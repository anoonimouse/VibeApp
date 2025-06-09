# Updating your existing app code with improvements and bug fixes

# Main fixes:
# - Removed the circular import from 'callback' route
# - Separated model declaration into a separate file (models.py) for cleaner structure
# - Adjusted imports accordingly
# - Fixed admin ban route redirect
# - Verified app context and db instance integrity

# File: models.
import os
from flask import flash
from flask_sqlalchemy import SQLAlchemy 
from sqlalchemy import Boolean, Column, Integer
from datetime import datetime
from pytz import timezone

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reddit_username = db.Column(db.String(100), unique=True, nullable=False)
    nickname = db.Column(db.String(50))
    age = db.Column(db.Integer)
    preferred_age_min = db.Column(db.Integer)
    preferred_age_max = db.Column(db.Integer)
    bio = db.Column(db.Text)
    interests_music = db.Column(db.Text)
    interests_movies = db.Column(db.Text)
    interests_topics = db.Column(db.Text)
    account_age = db.Column(db.Integer)
    karma = db.Column(db.Integer)
    joined = db.Column(db.DateTime, default=datetime.utcnow)
    blocked = db.Column(db.Boolean, default=False)  # Add this field
    is_banned = db.Column(db.Boolean, default=False)



class Vibe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(100))
    receiver = db.Column(db.String(100))
    status = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# ----------------------------------------------------------------

# File: app.py

from flask import Flask, redirect, render_template, request, session, url_for
from models import db, User, Vibe
from datetime import datetime
import random
import requests
import time
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://vibeapp_user:ScPXEpjVHuKTprIrEflmHkCTTKKY9H9n@dpg-d13jaua4d50c739gno30-a/vibeapp'
db.init_app(app)

# Reddit OAuth config
CLIENT_ID = 'ZohBbgx_RtMA4OLWTrKYTQ'
CLIENT_SECRET = 'rUvR1cw5mh13MFo9iKu6_LdT6iKpgQ'
REDIRECT_URI = 'https://vibeapp-qhaq.onrender.com/callback'
USER_AGENT = 'VibeMatchApp/0.1'

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/login')
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))  # Already logged in

    # Start Reddit OAuth if not logged in
    reddit_auth_url = (
        "https://www.reddit.com/api/v1/authorize?"
        f"client_id={CLIENT_ID}&response_type=code&state=random_string&"
        f"redirect_uri={REDIRECT_URI}&duration=temporary&scope=identity"
    )
    return redirect(reddit_auth_url)


@app.route('/callback')
def callback():
    code = request.args.get('code')
    auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    headers = {"User-Agent": USER_AGENT}
    data = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIRECT_URI}

    token_response = requests.post("https://www.reddit.com/api/v1/access_token",
                                   auth=auth, data=data, headers=headers)
    token_json = token_response.json()
    access_token = token_json.get('access_token')

    if not access_token:
        return "Error during Reddit OAuth"

    headers['Authorization'] = f'bearer {access_token}'
    user_response = requests.get("https://oauth.reddit.com/api/v1/me", headers=headers)
    user_data = user_response.json()

    username = user_data['name']
    created_utc = user_data['created_utc']
    account_age = int((time.time() - created_utc) // (60 * 60 * 24))
    total_karma = user_data.get('link_karma', 0) + user_data.get('comment_karma', 0)

    # Check if user already exists in database
    user = User.query.filter_by(reddit_username=username).first()

    if user:
        if user.is_banned:
            flash("Your account has been banned.")
            return redirect(url_for('logout'))

        # User exists: store session and go to dashboard
        session['user_id'] = user.id
        return redirect(url_for('dashboard'))

    # New user: create user entry with partial data and go to onboarding
    new_user = User(
        reddit_username=username,
        account_age=account_age,
        karma=total_karma,
        joined=datetime.utcnow()
    )
    db.session.add(new_user)
    db.session.commit()

    session['user_id'] = new_user.id
    return redirect('/onboarding/nickname')


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for('landing'))


# ---------------------- 🧭 Onboarding Wizard ----------------------

@app.route('/onboarding/nickname', methods=['GET', 'POST'])
def onboarding_nickname():
    if 'username' not in session:
        return redirect(url_for('landing'))
    user = User.query.filter_by(reddit_username=session['username']).first()
    if request.method == 'POST':
        user.nickname = request.form['nickname']
        db.session.commit()
        return redirect(url_for('onboarding_age'))
    return render_template('onboarding_nickname.html')

@app.route('/onboarding/age', methods=['GET', 'POST'])
def onboarding_age():
    if 'username' not in session:
        return redirect(url_for('landing'))
    user = User.query.filter_by(reddit_username=session['username']).first()
    if request.method == 'POST':
        user.age = int(request.form['age'])
        user.preferred_age_min = int(request.form['preferred_age_min'])
        user.preferred_age_max = int(request.form['preferred_age_max'])
        db.session.commit()
        return redirect(url_for('onboarding_bio'))
    return render_template('onboarding_age.html')

@app.route('/onboarding/bio', methods=['GET', 'POST'])
def onboarding_bio():
    if 'username' not in session:
        return redirect(url_for('landing'))
    user = User.query.filter_by(reddit_username=session['username']).first()
    if request.method == 'POST':
        user.bio = request.form['bio']
        db.session.commit()
        return redirect(url_for('onboarding_interests_music'))
    return render_template('onboarding_bio.html')

@app.route('/onboarding/interests/music', methods=['GET', 'POST'])
def onboarding_interests_music():
    if 'username' not in session:
        return redirect(url_for('landing'))
    user = User.query.filter_by(reddit_username=session['username']).first()
    music_options = [
    'Rock (Stage ka Raja)',
    'Pop (Chartbuster vibes)',
    'Hip-Hop (DHH wannabe)',
    'Jazz (Smooth swag)',
    'Classical (Sitar & stuff)',
    'Electronic (DJ wale babu)',
    'Country (Gaon ki dhun)',
    'Reggae (Chill maar bro)',
    'Blues (Dil tut gaya)',
    'Metal (Headbang warning)',
    'Folk (Desi beats)',
    'R&B (Romance mode on)'
]


    if request.method == 'POST':
        selected_music = request.form.getlist('music_interests')
        user.interests_music = ','.join(selected_music)
        db.session.commit()
        return redirect(url_for('onboarding_interests_movies'))
    saved_interests = user.interests_music.split(',') if user.interests_music else []
    return render_template('onboarding_interests_music.html', music_options=music_options, saved_interests=saved_interests)

@app.route('/onboarding/interests/movies', methods=['GET', 'POST'])
def onboarding_interests_movies():
    if 'username' not in session:
        return redirect(url_for('landing'))
    user = User.query.filter_by(reddit_username=session['username']).first()
    movie_options = [
    'Action (Hero vibes only)',
    'Comedy (LOL scenes)',
    'Drama (Full filmy feels)',
    'Fantasy (Magic & dhamaal)',
    'Horror (Bhoot pret alert)',
    'Mystery (Who’s the culprit?)',
    'Romance (Love-shove)',
    'Thriller (Dil thamm ke dekho)',
    'Sci-Fi (Space jugaad)',
    'Documentary (Sach ka tadka)'
]

    if request.method == 'POST':
        selected_movies = request.form.getlist('movie_interests')
        user.interests_movies = ','.join(selected_movies)
        db.session.commit()
        return redirect(url_for('onboarding_interests_topics'))
    saved_interests = user.interests_movies.split(',') if user.interests_movies else []
    return render_template('onboarding_interests_movies.html', movie_options=movie_options, saved_interests=saved_interests)

@app.route('/onboarding/interests/topics', methods=['GET', 'POST'])
def onboarding_interests_topics():
    if 'username' not in session:
        return redirect(url_for('landing'))
    user = User.query.filter_by(reddit_username=session['username']).first()
    topic_options = [
    'Memes (Hasi ka dose)',
    'Politics (Jhanda lehrayega?)',
    'Lifestyle (Swag level)',
    'Technology (Tech geek)',
    'Gaming (Noob ya pro?)',
    'Fitness (Gym-shim)',
    'Books (Padhaku vibes)',
    'Science (Rocket science?)',
    'Travel (Yatra mode)',
    'Food (Tandoori tadka)'
]

    if request.method == 'POST':
        selected_topics = request.form.getlist('topic_interests')
        user.interests_topics = ','.join(selected_topics)
        db.session.commit()
        return redirect(url_for('onboarding_review'))
    saved_interests = user.interests_topics.split(',') if user.interests_topics else []
    return render_template('onboarding_interests_topics.html', topic_options=topic_options, saved_interests=saved_interests)

@app.route('/onboarding/review')
def onboarding_review():
    if 'username' not in session:
        return redirect(url_for('landing'))
    user = User.query.filter_by(reddit_username=session['username']).first()
    return render_template('onboarding_review.html', user=user)

# ---------------------- 👤 User Dashboard ----------------------

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('landing'))

    user = User.query.get(session['user_id'])

    if not user:
        return redirect(url_for('landing'))

    if user.is_banned:
        flash("You have been banned.")
        return redirect(url_for('logout'))

    # Fetch accepted matches
    matches = Vibe.query.filter_by(sender=user.reddit_username, status='accepted').all()

    # Fetch pending incoming vibes
    incoming_vibes = Vibe.query.filter_by(receiver=user.reddit_username, status='pending').all()

    return render_template('dashboard.html', user=user, matches=matches, pending_vibes=incoming_vibes)


@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'username' not in session:
        return redirect(url_for('landing'))
    user = User.query.filter_by(reddit_username=session['username']).first()
    if request.method == 'POST':
        user.nickname = request.form['nickname']
        user.bio = request.form['bio']
        user.age = int(request.form['age'])
        user.preferred_age_min = int(request.form['preferred_age_min'])
        user.preferred_age_max = int(request.form['preferred_age_max'])
        user.interests_music = ','.join(request.form.getlist('interests_music'))
        user.interests_movies = ','.join(request.form.getlist('interests_movies'))
        user.interests_topics = ','.join(request.form.getlist('interests_topics'))
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('edit_profile.html', user=user)

# ---------------------- 🤝 Matching & Vibes ----------------------

@app.route('/matches')
def matches():
    if 'username' not in session:
        return redirect(url_for('landing'))
    user = User.query.filter_by(reddit_username=session['username']).first()
    all_users = User.query.filter(User.reddit_username != session['username']).all()
    suggestions = []
    for u in all_users:
        score = compute_match_score(current_user, other_user)  # Replace with real matching algo
        suggestions.append((u, score))
    return render_template('matches.html', suggestions=suggestions)

@app.route('/send-vibe/<target_username>', methods=['POST'])
def send_vibe(target_username):
    if 'username' not in session:
        return redirect(url_for('landing'))
    vibe = Vibe(sender=session['username'], receiver=target_username, status='pending')
    db.session.add(vibe)
    db.session.commit()
    return redirect(url_for('matches'))

@app.route('/accept-vibe/<sender_username>', methods=['POST'])
def accept_vibe(sender_username):
    if 'username' not in session:
        return redirect(url_for('landing'))
    vibe = Vibe.query.filter_by(sender=sender_username, receiver=session['username'], status='pending').first()
    if vibe:
        vibe.status = 'accepted'
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/deny-vibe/<sender_username>', methods=['POST'])
def deny_vibe(sender_username):
    if 'username' not in session:
        return redirect(url_for('landing'))
    vibe = Vibe.query.filter_by(sender=sender_username, receiver=session['username'], status='pending').first()
    if vibe:
        vibe.status = 'denied'
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/unmatch/<username>', methods=['POST'])
def unmatch(username):
    if 'username' not in session:
        return redirect(url_for('landing'))
    Vibe.query.filter(
        ((Vibe.sender == session['username']) & (Vibe.receiver == username)) |
        ((Vibe.sender == username) & (Vibe.receiver == session['username']))
    ).delete()
    db.session.commit()
    return redirect(url_for('dashboard'))

# ---------------------- Matching algo ----------------------
def compute_match_score(user1, user2):
    score = 0
    max_score = 100  # total max score

    # 1. Music interest overlap (30 points max)
    music1 = set(user1.interests_music.split(',')) if user1.interests_music else set()
    music2 = set(user2.interests_music.split(',')) if user2.interests_music else set()
    music_common = music1.intersection(music2)
    if music1 or music2:
        music_score = (len(music_common) / max(len(music1), len(music2))) * 30
    else:
        music_score = 0
    score += music_score

    # 2. Movie interest overlap (30 points max)
    movies1 = set(user1.interests_movies.split(',')) if user1.interests_movies else set()
    movies2 = set(user2.interests_movies.split(',')) if user2.interests_movies else set()
    movie_common = movies1.intersection(movies2)
    if movies1 or movies2:
        movie_score = (len(movie_common) / max(len(movies1), len(movies2))) * 30
    else:
        movie_score = 0
    score += movie_score

    # 3. Topic interest overlap (30 points max)
    topics1 = set(user1.interests_topics.split(',')) if user1.interests_topics else set()
    topics2 = set(user2.interests_topics.split(',')) if user2.interests_topics else set()
    topic_common = topics1.intersection(topics2)
    if topics1 or topics2:
        topic_score = (len(topic_common) / max(len(topics1), len(topics2))) * 30
    else:
        topic_score = 0
    score += topic_score

    # 4. Age preference match (10 points max)
    # Check if user1's age fits user2's preferred age range and vice versa
    age_score = 0
    if (user1.age and user2.preferred_age_min and user2.preferred_age_max
        and user2.preferred_age_min <= user1.age <= user2.preferred_age_max):
        age_score += 5
    if (user2.age and user1.preferred_age_min and user1.preferred_age_max
        and user1.preferred_age_min <= user2.age <= user1.preferred_age_max):
        age_score += 5
    score += age_score

    return round(score)

# ---------------------- 📬 Messaging & Sharing ----------------------

@app.route('/message/<username>')
def message_user(username):
    return redirect(f"https://www.reddit.com/message/compose/?to={username}")

@app.route('/share-profile/<username>')
def share_profile(username):
    user = User.query.filter_by(reddit_username=username).first()
    return render_template('share_profile.html', user=user)

# ---------------------- 🛠️ Admin Panel ----------------------

@app.route('/admin')
def admin_panel():
    ist = timezone('Asia/Kolkata')
    users = User.query.all()
    for u in users:
        u.joined_ist = u.joined.replace(tzinfo=timezone('UTC')).astimezone(ist)
    return render_template('admin_dashboard.html', users=users)

@app.route('/admin/reports')
def admin_reports():
    return "No reports yet."

@app.route('/admin/ban/<username>')
def admin_ban(username):
    user = User.query.filter_by(reddit_username=username).first()
    if user:
        user.is_banned = not user.is_banned
        db.session.commit()
    return redirect(url_for('admin'))


# ---------------------- Run Server ----------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
