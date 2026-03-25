from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, PasswordField, SelectField
from wtforms.validators import DataRequired, Length, EqualTo, Email

class QuestionForm(FlaskForm):
    subject = StringField('제목', validators=[DataRequired('제목은 필수 입력 항목입니다.')])
    content = TextAreaField('내용', validators=[DataRequired('내용은 필수 입력 항목입니다.')])

class AnswerForm(FlaskForm):
    content = TextAreaField('내용', validators=[DataRequired('내용은 필수 입력 항목입니다.')])

class UserCreateForm(FlaskForm):
    email = StringField('이메일', validators=[DataRequired(), Email()])
    birth_year = SelectField('출생연도', coerce=int, validators=[DataRequired()],
                             choices=[(year, f"{year}년") for year in range(2026, 1949, -1)])
    district = SelectField('관심 지역구', validators=[DataRequired()],
                           choices=[
                               ('강남구', '강남구'), ('강동구', '강동구'), ('강북구', '강북구'),
                               ('강서구', '강서구'), ('관악구', '관악구'), ('광진구', '광진구'),
                               ('구로구', '구로구'), ('금천구', '금천구'), ('노원구', '노원구'),
                               ('도봉구', '도봉구'), ('동대문구', '동대문구'), ('동작구', '동작구'),
                               ('마포구', '마포구'), ('서대문구', '서대문구'), ('서초구', '서초구'),
                               ('성동구', '성동구'), ('성북구', '성북구'), ('송파구', '송파구'),
                               ('양천구', '양천구'), ('영등포구', '영등포구'), ('용산구', '용산구'),
                               ('은평구', '은평구'), ('종로구', '종로구'), ('중구', '중구'), ('중랑구', '중랑구')
                           ])
    disease = SelectField('기저질환', validators=[DataRequired()],
                          choices=[
                              ('none', '없음'),
                              ('asthma', '천식'),
                              ('rhinitis', '비염'),
                              ('copd', '만성폐쇄성폐질환(COPD)'),
                              ('etc', '기타 호흡기 질환')
                          ])
    username = StringField('아이디', validators=[DataRequired(), Length(min=3, max=25)])
    password1 = PasswordField('비밀번호', validators=[
        DataRequired(), EqualTo('password2', '비밀번호가 일치하지 않습니다.')])
    password2 = PasswordField('비밀번호확인', validators=[DataRequired()])

class UserLoginForm(FlaskForm):
    username = StringField('아이디', validators=[DataRequired(), Length(min=3, max=25)])
    password = PasswordField('비밀번호', validators=[DataRequired()])