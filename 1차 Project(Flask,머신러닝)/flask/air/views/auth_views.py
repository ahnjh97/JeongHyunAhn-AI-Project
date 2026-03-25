from flask import Blueprint, url_for, render_template, request, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import redirect
from air import db
from air.forms import UserCreateForm, UserLoginForm
from air.models import Users
import random
from sqlalchemy import select

bp = Blueprint('auth', __name__, url_prefix='/auth')

# [STEP 1] 이메일 중복 확인 및 인증 코드 전송
@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')

        # SQLAlchemy 2.0 방식 조회
        stmt = select(Users).where(Users.email == email)
        existing_user = db.session.execute(stmt).scalar_one_or_none()

        if existing_user:
            flash("이미 가입된 이메일입니다.")
            return redirect(url_for('auth.signup'))

        # 기존에 남아있을지 모를 세션 데이터를 깔끔하게 초기화
        session.pop('signup_temp', None)
        session.pop('auth_verified', None)

        # 인증 코드 생성 (예: 6자리 숫자)
        auth_code = str(random.randint(100000, 999999))

        # 이메일 발송 로직 (여기에 SMTP 등을 이용한 발송 코드 추가)
        # send_email(email, auth_code)

        # 세션에 임시 저장
        session['signup_temp'] = {'email': email, 'code': auth_code}
        return redirect(url_for('auth.signup_email'))

    return render_template('auth/signup.html')

# [STEP 2] 인증코드 6자리 입력
@bp.route('/signup-email', methods=['GET', 'POST'])
def signup_email():
    if 'signup_temp' not in session:
        return redirect(url_for('auth.signup'))

    if request.method == 'POST':
        user_code = request.form.get('auth_code')
        correct_code = session['signup_temp'].get('code')

        if user_code == correct_code:
            session['auth_verified'] = True  # 인증 성공 표시
            return redirect(url_for('auth.signup_info'))
        else:
            flash("인증번호가 일치하지 않습니다.")

    return render_template('auth/signup_email.html')

# [STEP 3] 상세 정보 입력 (ID, PW, 출생연도, 지역구, 기저질환)
@bp.route('/signup-info', methods=['GET', 'POST'])
def signup_info():
    form = UserCreateForm()  # 폼 객체 생성

    # [보안] 2단계 인증 여부 확인
    if not session.get('auth_verified'):
        flash("이메일 인증이 필요합니다.")
        return redirect(url_for('auth.signup'))

    if request.method == 'POST' and form.validate_on_submit():
        # 1. 폼 데이터 가져오기
        user_id = form.username.data
        password = form.password1.data  # UserCreateForm 정의에 맞게 수정 (password1 등)
        birth_year = form.birth_year.data
        district = form.district.data
        disease = form.disease.data

        # 3. 아이디 중복 확인 (SQLAlchemy 2.0 방식)
        stmt = select(Users).where(Users.username == user_id)
        existing_user = db.session.execute(stmt).scalar_one_or_none()

        if existing_user:
            flash("이미 존재하는 아이디입니다.")
            return render_template('auth/signup_info.html', form=form)

        # 4. 최종 DB 저장 로직 (1단계 세션 이메일 + 3단계 입력 정보)
        try:
            email = session['signup_temp']['email']  # 1단계에서 저장한 이메일

            new_user = Users(
                birth_year=birth_year,
                district=district,
                disease=disease,
                email=email,
                username=user_id,
                password=generate_password_hash(password) # 해싱하여 저장
            )

            db.session.add(new_user)
            db.session.commit()

            # 5. 가입 성공 후 세션 데이터 삭제 (청소)
            session.pop('signup_temp', None)
            session.pop('auth_verified', None)

            flash("회원가입이 완료되었습니다. 로그인해주세요!")
            return redirect(url_for('main.index'))

        except Exception as e:
            db.session.rollback()
            flash("가입 중 오류가 발생했습니다. 다시 시도해주세요.")
            print(f"Error: {e}")

    # GET 요청 시 혹은 유효성 검사 실패 시
    return render_template('auth/signup_info.html', form=form)

@bp.route('/login/', methods=['GET', 'POST'])
def login():
    form = UserLoginForm()
    if request.method == 'POST' and form.validate_on_submit(): # 로그인 사용자 정보를 입력한 경우
        error = None
        user = Users.query.filter_by(username=form.username.data).first()
        if not user or not check_password_hash(user.password, form.password.data):
            error = "아이디 또는 비밀번호가 일치하지 않습니다."

        if error is None:
            session.clear()
            session['user_id'] = user.id
            return redirect(url_for('main.index'))
        flash(error)
    return render_template('auth/login.html', form=form) # 처음 /login으로 온 경우

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = Users.query.get(user_id)

@bp.route('/logout/')
def logout():
    session.clear()
    return redirect(url_for('main.index'))