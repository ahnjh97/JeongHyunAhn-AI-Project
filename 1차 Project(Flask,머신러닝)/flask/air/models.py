from air import db

class Question(db.Model):
    __tablename__ = 'question'
    id = db.Column(db.Integer, db.Sequence('question_seq', start=1, increment=1), primary_key=True)
    subject = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text(), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)

class Answer(db.Model):
    __tablename__ = 'answer'

    # Oracle에서 자동 증가를 위해 시퀀스를 사용
    id = db.Column(db.Integer, db.Sequence('answer_seq', start=1, increment=1), primary_key=True)

    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'))
    #question 속성은 Answer가 연결된 Question 객체를 가리킴
    question = db.relationship('Question', backref=db.backref('answer_set'))

    content = db.Column(db.Text(), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)

class Users(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, db.Sequence('users_seq', start=1, increment=1), primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    birth_year = db.Column(db.Integer)
    district = db.Column(db.String(50))
    disease = db.Column(db.String(100))