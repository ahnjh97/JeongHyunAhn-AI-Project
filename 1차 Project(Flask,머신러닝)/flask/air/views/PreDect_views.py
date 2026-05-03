from flask import Blueprint, render_template

bp = Blueprint('PreDect', __name__, url_prefix='/')

@bp.route('/PreDect')
def PreDect():
    return render_template('PreDect.html')