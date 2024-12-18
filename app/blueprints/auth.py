from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models.user import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()  
        if user and user.check_password(password):
            session['logged_in'] = True
            session['user_id'] = user.id
            #session['test_case_list'] = []  
            return redirect(url_for('staffedit.proDashboard'))
        else:
            flash('Username or password incorrect')

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('user_id', None)
    flash('Successfully logged out')
    return redirect(url_for('auth.login'))
