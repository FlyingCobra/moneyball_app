from flask import render_template, flash, redirect, url_for, request
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.urls import url_parse

from app import app, db
from app.models import User, Match, UserMatch, Rating
from app.forms import LoginForm, RegistrationForm, CreateMatchForm
from app.plots import plot_ratings, components

@app.route('/')
@app.route('/index')
def index():
    users = User.query.all()
    users = sorted(users, key=lambda u: u.get_current_elo(), reverse=True)
    return render_template('index.html', title='Home', users=users)

@app.route('/login', methods=['GET', 'POST'])
def login():
    # If already logged in, sent to frontpage
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password.')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign in', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        r_elo = Rating(user=user, rating_type='elo', rating_value=1500)
        r_ts_m = Rating(user=user, rating_type='trueskill_mu', rating_value=25)
        r_ts_s = Rating(user=user, rating_type='trueskill_sigma', rating_value=8.333)
        db.session.add(r_elo)
        db.session.add(r_ts_m)
        db.session.add(r_ts_s)
        db.session.commit()
        flash('Congratulations! You are registered.')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    plot = plot_ratings(username, 'elo')
    b_script, b_div = components(plot)
    return render_template('user.html', user=user, matches=user.matches, b_script=b_script, b_div=b_div)


@app.route('/match/<match_id>')
def match(match_id):
    match = Match.query.filter_by(id=match_id).first_or_404()
    return render_template('view_match.html', title='Match details', match=match)


@app.route('/create_match', methods=['GET', 'POST'])
@login_required
def create_match():
    if not current_user.is_authenticated:
        flash('You have to login before creating a match.')
        return redirect(url_for('index'))
    form = CreateMatchForm()
    if form.validate_on_submit():
        match = Match(
            winner_score=form.winner_score.data, 
            loser_score=form.loser_score.data,
            importance=form.importance.data)
        db.session.add(match)
        db.session.flush()

        for w in form.winners.data:
            user_match = UserMatch(
                user=w,
                match=match, 
                win=True)
            db.session.add(user_match)
        for l in form.losers.data:
            user_match = UserMatch(
                user=l,
                match=match, 
                win=False)
            db.session.add(user_match)
        db.session.flush()
        
        elo_change = get_match_elo_change(match)
        for p in form.winners.data:
            r = Rating(user=p, match=match, rating_type='elo', rating_value=p.get_current_elo() + elo_change)
            db.session.add(r)
        for p in form.losers.data:
            r = Rating(user=p, match=match, rating_type='elo', rating_value=p.get_current_elo() - elo_change)
            db.session.add(r)
        db.session.commit()
        flash('Match created')
        return redirect(url_for('login'))
    return render_template('create_match.html', title='Create match', form=form)


def get_match_elo_change(match):
    Qs = []
    for players in [match.winning_players, match.losing_players]:
        elos = [p.get_current_elo() for p in players]
        avg_elo = sum(elos) / len(elos)
        Q = 10 ** (avg_elo / 400)
        Qs.append(Q)
    Q_w, Q_l = Qs
    exp_win = Q_w / (Q_w + Q_l)
    change_w = match.importance * (1 - exp_win)
    return change_w