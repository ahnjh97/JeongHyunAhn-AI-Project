from flask import Blueprint, render_template, request, url_for
from air.models import Question
from ..forms import QuestionForm, AnswerForm
from datetime import datetime
from werkzeug.utils import redirect
from .. import db

bp = Blueprint('question', __name__, url_prefix='/question')

@bp.route('/list/')
def _list():
    page = request.args.get('page', type=int, default=1)
    question_list = Question.query.order_by(Question.create_date.desc())
    question_list = question_list.paginate(page=page, per_page=10)
    return render_template('question/question_list.html', question_list=question_list)

@bp.route('/detail/<int:question_id>/')
def detail(question_id):
    form = AnswerForm()
    question = Question.query.get_or_404(question_id)
    return render_template('question/question_detail.html', question=question, form=form)

@bp.route('/create/', methods=['GET', 'POST'])
def create():
    # 1) QuestionForm 클래스의 인스턴스를 생성 (forms.py에서 정의)
    form = QuestionForm()

    # 2) 현재 요청이 POST 방식이고, 폼 유효성 검사(Flask-WTF)가 통과했는지 확인
    if request.method == 'POST' and form.validate_on_submit():
        # 3) 유효한 폼 데이터로 Question 모델 인스턴스생성
        question = Question(
            subject=form.subject.data, # 폼에서 입력된 '제목'
            content=form.content.data, # 폼에서 입력된 '내용'
            create_date=datetime.now()  # 현재 시각을 생성일로 설정
        )

        # 4) DB 세션에 question 객체 추가 후 커밋 -> 실제 DB에 저장
        db.session.add(question)
        db.session.commit()

        # 5) 등록 후 메인 페이지 (main.index)로 리다이렉트
        return redirect(url_for('main.index'))

    # 6) GET 요청이거나 폼 검증에 실패한 경우 -> 질문 등록 템플릿 재렌더링
    return render_template('/question/question_form.html', form=form)