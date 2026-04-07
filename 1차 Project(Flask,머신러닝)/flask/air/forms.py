from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, PasswordField, SelectField, FloatField, IntegerField
from wtforms.validators import DataRequired, Length, EqualTo, Email, Optional, NumberRange

class QuestionForm(FlaskForm):
    subject = StringField('제목', validators=[DataRequired('제목은 필수 입력 항목입니다.')])
    content = TextAreaField('내용', validators=[DataRequired('내용은 필수 입력 항목입니다.')])

class AnswerForm(FlaskForm):
    content = TextAreaField('내용', validators=[DataRequired('내용은 필수 입력 항목입니다.')])

class ProfileForm(FlaskForm):
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

class AccountForm(FlaskForm):
    username = StringField('아이디', validators=[DataRequired(), Length(min=3, max=25)])
    password1 = PasswordField('비밀번호', [
        DataRequired(),
        Length(min=8, message='비밀번호는 8자 이상이어야 합니다.')
    ])
    password2 = PasswordField('비밀번호 확인', [
        DataRequired(),
        # password1과 일치하는지 확인하고, 에러 시 password2 필드 에러로 처리
        EqualTo('password1', message='비밀번호가 일치하지 않습니다.')
    ])

class UserLoginForm(FlaskForm):
    username = StringField('아이디', validators=[DataRequired(), Length(min=3, max=25)])
    password = PasswordField('비밀번호', validators=[DataRequired()])

class SimulationForm(FlaskForm):
    dist_name = StringField('자치구 이름', validators=[DataRequired()])
    disease_type = StringField('질병', validators=[DataRequired()])

    # 소수점 입력이 가능한 숫자 필드 (기본값 설정 가능)
    pm10_3avg = FloatField('PM10 3일 평균', validators=[Optional()], default=42.0)
    pm25_3avg = FloatField('PM25 3일 평균', validators=[Optional()], default=22.0)

    # 정수만 입력받고 싶을 때 (예: 과거 환자 수)
    lag1 = IntegerField('1일 전 환자수', validators=[Optional()], default=0)
    lag2 = IntegerField('2일 전 환자수', validators=[Optional()], default=0)
    lag3 = IntegerField('3일 전 환자수', validators=[Optional()], default=0)

    # 범위 제한이 필요한 경우 (예: 비율은 0~1 사이)
    child_ratio = FloatField('아동 비율', validators=[NumberRange(min=0, max=50)], default=10)
    old_ratio = FloatField('노인 비율', validators=[NumberRange(min=0, max=50)], default=17)

    temp_diff = FloatField('일교차', default=0)
    grdp_pc = IntegerField('1인당 GRDP', default=45000)