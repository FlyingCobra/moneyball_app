from app import db
from app.models import User, Rating, Match, UserMatch
from datetime import datetime
import trueskill as ts

def create_user(shortname, nickname, password):
    sn_user = User.query.filter(User.shortname == shortname.upper()).first()
    nn_user = User.query.filter(User.nickname == nickname).first()
    if sn_user is not None:
        raise AssertionError('Someone has already used that shortname')
    if nn_user is not None:
        raise AssertionError('Someone has already used that nickname')
    
    user = User(
        shortname=shortname.upper(),
        nickname=nickname
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    init_ratings(user)
    return user

def init_ratings(user, timestamp=None):
    if timestamp is None:
        timestamp = datetime.now()
    r_elo = Rating(user=user, rating_type='elo', rating_value=1500, 
        timestamp=timestamp)
    r_ts_m = Rating(user=user, rating_type='trueskill_mu', 
        rating_value=25, timestamp=timestamp)
    r_ts_s = Rating(user=user, rating_type='trueskill_sigma', 
        rating_value=8.333, timestamp=timestamp)
    db.session.add_all([r_elo, r_ts_m, r_ts_s])
    db.session.commit()

def recalculate_ratings():
    users = User.query.all()
    timestamps = []
    for u in users:
        # Get the first timestamp on Rating for each User
        # To initialize first Rating at earliest record of the user. 
        timestamps.append(Rating.query \
            .filter(Rating.user_id == u.id) \
            .filter(Rating.rating_type == 'elo') \
            .order_by(Rating.timestamp) \
            .first().timestamp )
    db.session.query(Rating).delete()
    db.session.commit()
    for u, t in zip(users, timestamps):
        init_ratings(u, t)

    matches = Match.query \
        .filter(Match.approved_winner == True) \
        .filter(Match.approved_loser == True) \
        .order_by(Match.timestamp).all()
    for match in matches:
        update_match_ratings(match)

def delete_match(match):
    db.session.delete(match)
    db.session.commit()
    recalculate_ratings()

def update_match_ratings(match):
    if not match.approved_winner or not match.approved_loser:
        # Don't update ratings, as match is not approved
        return False
    update_trueskill_by_match(match)
    update_elo_by_match(match)

def update_elo_by_match(match):
    elo_change = get_match_elo_change(match)
    for p in match.winning_players:
        r = Rating(user=p, match=match, rating_type='elo', 
        rating_value=p.get_current_elo() + elo_change,
        timestamp=match.timestamp)
        db.session.add(r)
    for p in match.losing_players:
        r = Rating(user=p, match=match, rating_type='elo',
        rating_value=p.get_current_elo() - elo_change,
        timestamp=match.timestamp)
        db.session.add(r)
    db.session.commit()

def update_trueskill_by_match(match):
    w_ratings = []
    l_ratings = []
    for p in match.winning_players:
        mu, sigma = p.get_current_trueskill()
        w_ratings.append(ts.Rating(mu, sigma))

    for p in match.losing_players:
        mu, sigma = p.get_current_trueskill()
        l_ratings.append(ts.Rating(mu, sigma))

    rating_groups = [w_ratings, l_ratings]
    new_ratings = ts.rate(rating_groups, ranks=[0,1])
    players = match.winning_players + match.losing_players
    new_ratings_flat = [item for sublist in new_ratings for item in sublist]
    for player, rating in zip(players, new_ratings_flat):
        r_m = Rating(
            user=player,
            match=match,
            rating_type='trueskill_mu',
            rating_value=rating.mu,
            timestamp=match.timestamp,
        )
        r_s = Rating(
            user=player,
            match=match,
            rating_type='trueskill_sigma',
            rating_value=rating.sigma,
            timestamp=match.timestamp,
        )
        db.session.add_all([r_m, r_s])
        db.session.commit()

def get_match_elo_change(match):
    Qs = []
    # First, get all winning players, then all losing players
    for players in [match.winning_players, match.losing_players]:
        # Get the avg elo for each team seperately
        elos = [p.get_current_elo() for p in players]
        avg_elo = sum(elos) / len(elos)
        Q = 10 ** (avg_elo / 400)
        Qs.append(Q)
    Q_w, Q_l = Qs
    exp_win = Q_w / (Q_w + Q_l)
    change_w = match.importance * (1 - exp_win)
    return change_w

def approve_match(match, approver):
    if approver in match.winning_players:
        match.approved_winner = True
    elif approver in match.losing_players:
        match.approved_loser = True
    else:
        # User not playing
        return 'Cant approve match. You are not a player in this match'
    db.session.commit()
    recalculate_ratings()
    return 'Match approved'

def make_new_match(winners, losers, w_score, l_score, importance, 
    user_creating_match=None):
    approved_winner, approved_loser = False, False
    if user_creating_match in winners:
        approved_winner = True
    elif user_creating_match in losers:
        approved_loser = True
    match = Match(
        winner_score=w_score, 
        loser_score=l_score,
        importance=importance,
        approved_winner=approved_winner,
        approved_loser=approved_loser)
    db.session.add(match)
    db.session.flush()

    for w in winners:
        user_match = UserMatch(
            user=w,
            match=match, 
            win=True)
        db.session.add(user_match)
    for l in losers:
        user_match = UserMatch(
            user=l,
            match=match, 
            win=False)
        db.session.add(user_match)
    db.session.flush()
    
    update_match_ratings(match)
    db.session.commit()
    return match


def update_user(user, shortname, nickname):
    user.shortname = shortname.upper()
    user.nickname = nickname
    db.session.commit()
    return user

def update_password(user, password):
    if password is not None:
        user.set_password(password)
    db.session.commit()
    return user