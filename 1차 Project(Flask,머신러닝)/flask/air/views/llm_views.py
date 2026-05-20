from flask import Blueprint, render_template

bp = Blueprint("llm", __name__, url_prefix="/llm")


@bp.route("/tutor")
def tutor():
    return render_template(
        "llm_tutor.html",
        llm_api_url="http://3.37.128.252:5000/chat",
    )
