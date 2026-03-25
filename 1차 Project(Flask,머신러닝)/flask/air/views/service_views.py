from flask import Blueprint, url_for, render_template
from werkzeug.utils import redirect

bp = Blueprint('service', __name__, url_prefix='/')

@bp.route('/service')
def service():
    return render_template('service.html')