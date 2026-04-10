from flask import Flask, render_template, redirect, url_for,request, flash
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from dotenv import load_dotenv
from wtforms import StringField, SubmitField
import psycopg
import gunicorn
import os 
from wtforms.validators import DataRequired, URL
from flask_ckeditor import CKEditor, CKEditorField
from datetime import date
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
import requests
from forms import PostForm, RegisterForm, LoginForm, CommentForm
from functools import wraps
from flask import abort

URL = "https://api.npoint.io/674f5423f73deab1e9a7"

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get('SECRET_KEY')
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
ckeditor = CKEditor(app)
Bootstrap5(app) 

class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DB_URI','sqlite:///posts.db')
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# CONFIGURE TABLE
class BlogPost(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(250), nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))

with app.app_context():
    db.create_all()

# with app.app_context():
#     response = requests.get(URL)
#     data = response.json()
#     existing_titles = {
#         title for (title,) in db.session.execute(
#             db.select(BlogPost.title)
#         ).all()
#     }
#     for item in data:
#         post = BlogPost(
#             title=item["title"],
#             subtitle=item["subtitle"],
#             body=item["body"],
#             author= "Anonymous",
#             img_url=item["img_url"],
#             date=date.today().strftime("%B %d, %Y")
#         )
#         db.session.add(post)

#     db.session.commit()

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        #If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        #Otherwise continue with the route function
        return f(*args, **kwargs)        
    return decorated_function

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route('/')
@login_required
def app_run():
    response = db.session.execute(db.select(BlogPost)).scalars().all()
    return render_template("index.html", posts=response)


@app.route('/about')
@login_required
def ret_about():
    return render_template("about.html")


@app.route('/contact', methods=["GET", "POST"])
def ret_contact():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        message = request.form["message"]
        if not name or not email or not phone or not message:
            return render_template("contact.html", msg_sent=False, error=True)
        print(name, email, phone, message)
        return render_template("contact.html", msg_sent=True)
    return render_template("contact.html", msg_sent=False)


@app.route('/post/<int:post_id>')
def show_post(post_id):
    req_post = db.get_or_404(BlogPost, post_id)
    comment_form = CommentForm()
    return render_template("post.html", post= req_post, form=comment_form)

@app.route("/new-post", methods=["POST","GET"])
@login_required
@admin_only
def new_post():
    form = PostForm() 
    if form.validate_on_submit():
        get_new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=form.author.data,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(get_new_post)
        db.session.commit()
        return redirect(url_for("app_run"))
    return render_template("make_post.html", form=form)

@app.route("/edit-post/<post_id>", methods=["GET","POST"])
@login_required
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = PostForm(
        title = post.title,
        subtitle = post.subtitle,
        img_url = post.img_url,
        author = post.author,
        body = post.body

    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data    
        db.session.commit()
        return redirect(url_for("app_run"))
    return render_template("make_post.html", form=edit_form, is_edit=True)

@app.route("/delete-post/<post_id>")
@login_required
@admin_only
def delete_post(post_id):
    del_post = db.get_or_404(BlogPost, post_id)
    db.session.delete(del_post)
    db.session.commit()
    return redirect (url_for("app_run"))


@app.route("/register", methods=["GET","POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        result = db.session.execute(db.select(User).where(User.email==form.email.data)).scalar()
        if result:
            flash("E-Mail Already in Use, Either Login or Use Another E-Mail")
            return redirect(url_for("login"))
        hashed_pass= generate_password_hash(form.password.data, method="pbkdf2:sha256", salt_length=8)
        new_reg_user = User(
            email = form.email.data,
            name = form.name.data,
            password = hashed_pass
        )
        db.session.add(new_reg_user)
        db.session.commit()
        login_user(new_reg_user)
        return redirect(url_for("app_run"))
    return render_template("register.html", form=form)

@app.route("/login", methods=["GET","POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        result = db.session.execute(db.select(User).where(User.email==email)).scalar()
        if not result:
            flash("User Does Not Exists!!")
            return render_template("login.html", form=form)
        elif not check_password_hash(result.password, password):
            flash("Wrong Password, Try Again")
            return render_template("login.html", form=form)
        else:
            login_user(result)
            return redirect(url_for("app_run"))
    return render_template("login.html", form=form)

@app.route("/logout", methods =["GET", "POST"])
def logout():
    logout_user()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)


