from flask import Blueprint, url_for, render_template, request, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import redirect
from air import db
from air.forms import AccountForm, ProfileForm, UserLoginForm
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

    # POST가 아닌 모든 경우(GET 등)는 여기서 처리
    mode = request.args.get('mode')

    existing_email = None
    # 오직 '수정 모드'로 들어왔을 때만 세션 값을 꺼냅니다.
    if mode == 'edit' and 'signup_temp' in session:
        existing_email = session['signup_temp'].get('email')

    return render_template('auth/signup.html', email=existing_email)


# [STEP 2] 인증코드 6자리 입력
@bp.route('/signup-email', methods=['GET', 'POST'])
def signup_email():
    if 'signup_temp' not in session:
        return redirect(url_for('auth.signup'))

    if request.method == 'POST':
        # 어떤 동작인지 확인 (버튼의 name 값 가져오기)
        action = request.form.get('action')

        # [케이스 A] 재전송 버튼을 눌렀을 때
        if action == 'resend':
            email = session['signup_temp'].get('email')
            new_code = str(random.randint(100000, 999999))

            # 세션의 코드 업데이트
            session['signup_temp']['code'] = new_code
            session.modified = True  # 세션 내부 딕셔너리 변경 시 명시적 저장

            # 여기에 메일 발송 코드 추가
            # send_email(email, new_code)

            flash("인증 코드가 재전송되었습니다.", "info")
            return render_template('auth/signup_email.html')

        # [케이스 B] 인증 확인 버튼을 눌렀을 때
        user_code = request.form.get('auth_code')
        correct_code = session['signup_temp'].get('code')

        # if user_code == correct_code:
        #     session['auth_verified'] = True # 인증 성공 표시
        #     return redirect(url_for('auth.signup_account'))
        # else:
        #     flash("인증 코드가 일치하지 않습니다.")
        return redirect(url_for('auth.signup_account'))

    return render_template('auth/signup_email.html')


# [STEP 3] 계정 설정 (ID, PW)
@bp.route('/signup-account', methods=['GET', 'POST'])
def signup_account():
    form = AccountForm()

    # [보안] 2단계 인증 여부 확인
    # if not session.get('auth_verified'):
    #     return redirect(url_for('auth.signup'))

    if request.method == 'POST' and form.validate_on_submit():
        user_id = form.username.data
        password = form.password1.data

        stmt = select(Users).where(Users.username == user_id)
        existing_user = db.session.execute(stmt).scalar_one_or_none()

        if existing_user:
            flash("이미 존재하는 아이디입니다.")
            return render_template('auth/signup_account.html', form=form)

            # 세션에 3단계 정보 누적 저장
        session['signup_temp']['username'] = user_id
        session['signup_temp']['password'] = generate_password_hash(password)
        session.modified = True

        return redirect(url_for('auth.signup_profile'))

    return render_template('auth/signup_account.html', form=form)


# [STEP 4] 상세 정보 입력 (출생연도, 지역구, 기저질환) 및 최종 저장
@bp.route('/signup-profile', methods=['GET', 'POST'])
def signup_profile():
    form = ProfileForm()

    if request.method == 'POST' and form.validate_on_submit():
        birth_year = form.birth_year.data
        district = form.district.data
        disease = form.disease.data

        # 최종 DB 저장 로직
        try:
            # 세션에 누적된 1단계(이메일) 및 3단계(계정) 데이터 취합
            temp = session['signup_temp']
            email = temp['email']
            user_id = temp['username']
            password_hash = temp['password']

            new_user = Users(
                birth_year=birth_year,
                district=district,
                disease=disease,
                email=email,
                username=user_id,
                password=password_hash
            )

            db.session.add(new_user)
            db.session.commit()

            # 가입 성공 후 세션 데이터 삭제
            session.pop('signup_temp', None)
            session.pop('auth_verified', None)

            # flash("회원 가입이 완료되었습니다. 로그인해주세요!")
            return redirect(url_for('main.index'))

        except Exception as e:
            db.session.rollback()
            # flash("가입 중 오류가 발생했습니다. 다시 시도해주세요.")
            print(f"Error: {e}")

    return render_template('auth/signup_profile.html', form=form)


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

def send_email(email, auth_code):
    pass