from flask import Flask, redirect, render_template, request, session, url_for, flash
from models import db, User, Vibe
from datetime import datetime
from pytz import timezone
import random
import requests
import time
import os

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    reddit_username = db.Column(db.String(50), unique=True, nullable=False)
    nickname = db.Column(db.String(50))
    age = db.Column(db.Integer)
    bio = db.Column(db.Text)
    preferred_age_min = db.Column(db.Integer)
    preferred_age_max = db.Column(db.Integer)
    interests_music = db.Column(db.Text)
    interests_movies = db.Column(db.Text)
    interests_topics = db.Column(db.Text)
    account_age = db.Column(db.Integer)
    karma = db.Column(db.Integer)
    joined = db.Column(db.DateTime, default=datetime.utcnow)
    is_banned = db.Column(db.Boolean, default=False)

class Vibe(db.Model):
    __tablename__ = 'vibes'
    
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(50), nullable=False)
    receiver = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, denied
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

with app.app_context():
    try:
        db.create_all()
        print("Database tables created/verified")
    except Exception as e:
        print(f"Database initialization error: {e}")
        
# Reddit OAuth config
CLIENT_ID = os.environ.get('REDDIT_CLIENT_ID')
CLIENT_SECRET = os.environ.get('REDDIT_CLIENT_SECRET')
REDIRECT_URI = os.environ.get('REDIRECT_URI')
USER_AGENT = 'VibeMatchApp/0.1'
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME')

# ---------------------- Authentication Routes ----------------------

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/login')
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))  # Already logged in

    # Start Reddit OAuth if not logged in
    reddit_auth_url = (
        "https://www.reddit.com/api/v1/authorize.compact?"
        f"client_id={CLIENT_ID}&response_type=code&state=random_string&"
        f"redirect_uri={REDIRECT_URI}&duration=permanent&scope=identity"
    )
    return redirect(reddit_auth_url)

@app.route('/callback')
def callback():
    print("=== CALLBACK ROUTE HIT ===")
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        print(f"OAuth error: {error}")
        flash(f"Authorization failed: {error}")
        return redirect(url_for('landing'))
    
    if not code:
        print("No authorization code received")
        flash("Authorization failed. No code received.")
        return redirect(url_for('landing'))
    
    print(f"Authorization code received: {code[:10]}...")
    
    auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    headers = {"User-Agent": USER_AGENT}
    data = {
        'grant_type': 'authorization_code', 
        'code': code, 
        'redirect_uri': REDIRECT_URI
    }

    try:
        print("Requesting access token...")
        token_response = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=auth, 
            data=data, 
            headers=headers,
            timeout=10
        )
        
        print(f"Token response status: {token_response.status_code}")
        print(f"Token response: {token_response.text}")
        
        if token_response.status_code != 200:
            print(f"Token request failed: {token_response.status_code}")
            flash("Failed to get access token from Reddit.")
            return redirect(url_for('landing'))
        
        token_json = token_response.json()
        access_token = token_json.get('access_token')

        if not access_token:
            print("No access token in response")
            flash("Error during Reddit OAuth. No access token received.")
            return redirect(url_for('landing'))

        print("Access token received, fetching user data...")
        headers['Authorization'] = f'bearer {access_token}'
        user_response = requests.get(
            "https://oauth.reddit.com/api/v1/me", 
            headers=headers,
            timeout=10
        )
        
        print(f"User response status: {user_response.status_code}")
        
        if user_response.status_code != 200:
            print(f"User data request failed: {user_response.status_code}")
            flash("Failed to get user data from Reddit.")
            return redirect(url_for('landing'))
        
        user_data = user_response.json()
        print(f"User data: {user_data}")

        username = user_data.get('name')
        if not username:
            print("No username in user data")
            flash("Failed to get username from Reddit.")
            return redirect(url_for('landing'))
        
        created_utc = user_data.get('created_utc', 0)
        account_age = int((time.time() - created_utc) // (60 * 60 * 24))
        total_karma = user_data.get('link_karma', 0) + user_data.get('comment_karma', 0)

        print(f"Processing user: {username}")
        
        # Check if user already exists in database
        user = User.query.filter_by(reddit_username=username).first()
        print(f"Existing user found: {user is not None}")

        if user:
            if user.is_banned:
                print(f"User {username} is banned")
                flash("Your account has been banned.")
                return redirect(url_for('landing'))

            # User exists: store session and go to dashboard
            session['user_id'] = user.id
            session['username'] = username
            print(f"Existing user logged in: {username}, redirecting to dashboard")
            return redirect(url_for('dashboard'))

        # New user: create user entry
        print("Creating new user...")
        new_user = User(
            reddit_username=username,
            account_age=account_age,
            karma=total_karma,
            joined=datetime.utcnow()
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            print(f"New user created with ID: {new_user.id}")
        except Exception as db_error:
            print(f"Database error creating user: {db_error}")
            db.session.rollback()
            flash("Database error. Please try again.")
            return redirect(url_for('landing'))

        session['user_id'] = new_user.id
        session['username'] = username
        print(f"New user session created, redirecting to onboarding")
        return redirect(url_for('onboarding_nickname'))

    except requests.exceptions.Timeout:
        print("Request timeout")
        flash("Request timeout. Please try again.")
        return redirect(url_for('landing'))
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        flash("Network error during authentication.")
        return redirect(url_for('landing'))
    except Exception as e:
        print(f"Unexpected error in callback: {e}")
        import traceback
        traceback.print_exc()
        flash("Error during authentication. Please try again.")
        return redirect(url_for('landing'))


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for('landing'))

# ---------------------- 🧭 Onboarding Wizard ----------------------

@app.route('/onboarding/nickname', methods=['GET', 'POST'])
def onboarding_nickname():
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('landing'))
    
    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip()
        if nickname:
            user.nickname = nickname
            db.session.commit()
            return redirect(url_for('onboarding_age'))
        else:
            flash("Please enter a nickname.")
    
    return render_template('onboarding_nickname.html', user=user)

@app.route('/onboarding/age', methods=['GET', 'POST'])
def onboarding_age():
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('landing'))
    
    if request.method == 'POST':
        try:
            age = int(request.form['age'])
            preferred_age_min = int(request.form['preferred_age_min'])
            preferred_age_max = int(request.form['preferred_age_max'])
            
            if age < 18 or age > 100:
                flash("Age must be between 18 and 100.")
                return render_template('onboarding_age.html', user=user)
            
            if preferred_age_min > preferred_age_max:
                flash("Minimum preferred age cannot be greater than maximum.")
                return render_template('onboarding_age.html', user=user)
            
            user.age = age
            user.preferred_age_min = preferred_age_min
            user.preferred_age_max = preferred_age_max
            db.session.commit()
            return redirect(url_for('onboarding_bio'))
        except ValueError:
            flash("Please enter valid ages.")
    
    return render_template('onboarding_age.html', user=user)

@app.route('/onboarding/bio', methods=['GET', 'POST'])
def onboarding_bio():
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('landing'))
    
    if request.method == 'POST':
        bio = request.form.get('bio', '').strip()
        if bio:
            user.bio = bio
            db.session.commit()
            return redirect(url_for('onboarding_interests_music'))
        else:
            flash("Please enter a bio.")
    
    return render_template('onboarding_bio.html', user=user)

@app.route('/onboarding/interests/music', methods=['GET', 'POST'])
def onboarding_interests_music():
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('landing'))
    
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
        if selected_music:
            user.interests_music = ','.join(selected_music)
            db.session.commit()
            return redirect(url_for('onboarding_interests_movies'))
        else:
            flash("Please select at least one music interest.")
    
    saved_interests = user.interests_music.split(',') if user.interests_music else []
    return render_template('onboarding_interests_music.html', 
                           music_options=music_options, saved_interests=saved_interests, user=user)

@app.route('/onboarding/interests/movies', methods=['GET', 'POST'])
def onboarding_interests_movies():
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('landing'))
    
    movie_options = [
        'Action (Hero vibes only)',
        'Comedy (LOL scenes)',
        'Drama (Full filmy feels)',
        'Fantasy (Magic & dhamaal)',
        'Horror (Bhoot pret alert)',
        'Mystery (Who\'s the culprit?)',
        'Romance (Love-shove)',
        'Thriller (Dil thamm ke dekho)',
        'Sci-Fi (Space jugaad)',
        'Documentary (Sach ka tadka)'
    ]

    if request.method == 'POST':
        selected_movies = request.form.getlist('movie_interests')
        if selected_movies:
            user.interests_movies = ','.join(selected_movies)
            db.session.commit()
            return redirect(url_for('onboarding_interests_topics'))
        else:
            flash("Please select at least one movie interest.")
    
    saved_interests = user.interests_movies.split(',') if user.interests_movies else []
    return render_template('onboarding_interests_movies.html', 
                           movie_options=movie_options, saved_interests=saved_interests, user=user)

@app.route('/onboarding/interests/topics', methods=['GET', 'POST'])
def onboarding_interests_topics():
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('landing'))
    
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
        if selected_topics:
            user.interests_topics = ','.join(selected_topics)
            db.session.commit()
            return redirect(url_for('onboarding_review'))
        else:
            flash("Please select at least one topic interest.")
    
    saved_interests = user.interests_topics.split(',') if user.interests_topics else []
    return render_template('onboarding_interests_topics.html', 
                           topic_options=topic_options, saved_interests=saved_interests, user=user)

@app.route('/onboarding/review')
def onboarding_review():
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('landing'))
    
    return render_template('onboarding_review.html', user=user)

# ---------------------- 👤 User Dashboard ----------------------

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('landing'))

    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('landing'))

    if user.is_banned:
        flash("You have been banned.")
        session.clear()
        return redirect(url_for('landing'))

    # Check if user has completed onboarding
    if not user.nickname or not user.age or not user.bio:
        return redirect(url_for('onboarding_nickname'))

    # Fetch accepted matches
    matches = db.session.query(Vibe).filter_by(sender=user.reddit_username, status='accepted').all()

    # Fetch pending incoming vibes
    incoming_vibes = db.session.query(Vibe).filter_by(receiver=user.reddit_username, status='pending').all()

    return render_template('dashboard.html', user=user, matches=matches, pending_vibes=incoming_vibes)

@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('landing'))
    
    if request.method == 'POST':
        try:
            user.nickname = request.form.get('nickname', '').strip()
            user.bio = request.form.get('bio', '').strip()
            user.age = int(request.form['age'])
            user.preferred_age_min = int(request.form['preferred_age_min'])
            user.preferred_age_max = int(request.form['preferred_age_max'])
            
            # Handle interests
            user.interests_music = ','.join(request.form.getlist('interests_music'))
            user.interests_movies = ','.join(request.form.getlist('interests_movies'))
            user.interests_topics = ','.join(request.form.getlist('interests_topics'))
            
            db.session.commit()
            flash("Profile updated successfully!")
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash("Error updating profile. Please check your inputs.")
    
    return render_template('edit_profile.html', user=user)

# ---------------------- 🤝 Matching & Vibes ----------------------

@app.route('/matches')
def matches():
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('landing'))
    
    # Get users within age preference and exclude banned users
    all_users = User.query.filter(
        User.reddit_username != user.reddit_username,
        User.is_banned == False,
        User.age >= user.preferred_age_min,
        User.age <= user.preferred_age_max,
        User.nickname.isnot(None),  # Only show users who completed onboarding
        User.bio.isnot(None)
    ).all()
    
    # Filter out users we've already sent vibes to
    sent_vibes = db.session.query(Vibe.receiver).filter_by(sender=user.reddit_username).all()
    sent_usernames = [vibe[0] for vibe in sent_vibes]
    
    suggestions = []
    for u in all_users:
        if u.reddit_username not in sent_usernames:
            # Simple scoring based on common interests
            score = calculate_match_score(user, u)
            suggestions.append((u, score))
    
    # Sort by score descending
    suggestions.sort(key=lambda x: x[1], reverse=True)
    
    return render_template('matches.html', suggestions=suggestions, user=user)

def calculate_match_score(user1, user2):
    """Calculate match score between two users based on common interests"""
    score = 0
    
    # Music interests
    if user1.interests_music and user2.interests_music:
        music1 = set(user1.interests_music.split(','))
        music2 = set(user2.interests_music.split(','))
        score += len(music1.intersection(music2)) * 10
    
    # Movie interests
    if user1.interests_movies and user2.interests_movies:
        movies1 = set(user1.interests_movies.split(','))
        movies2 = set(user2.interests_movies.split(','))
        score += len(movies1.intersection(movies2)) * 10
    
    # Topic interests
    if user1.interests_topics and user2.interests_topics:
        topics1 = set(user1.interests_topics.split(','))
        topics2 = set(user2.interests_topics.split(','))
        score += len(topics1.intersection(topics2)) * 10
    
    # Age compatibility
    age_diff = abs(user1.age - user2.age)
    if age_diff <= 2:
        score += 20
    elif age_diff <= 5:
        score += 10
    elif age_diff <= 10:
        score += 5
    
    # Add some randomness to prevent always showing same order
    score += random.randint(0, 20)
    
    return round(score / 3, 2)

@app.route('/send-vibe/<target_username>', methods=['POST'])
def send_vibe(target_username):
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('landing'))
    
    # Check if vibe already exists
    existing_vibe = Vibe.query.filter_by(
        sender=user.reddit_username, 
        receiver=target_username
    ).first()
    
    if not existing_vibe:
        vibe = Vibe(sender=user.reddit_username, receiver=target_username, status='pending')
        db.session.add(vibe)
        db.session.commit()
        flash(f"Vibe sent to {target_username}!")
    else:
        flash("You've already sent a vibe to this user.")
    
    return redirect(url_for('matches'))

@app.route('/accept-vibe/<sender_username>', methods=['POST'])
def accept_vibe(sender_username):
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('landing'))
    
    vibe = Vibe.query.filter_by(
        sender=sender_username, 
        receiver=user.reddit_username, 
        status='pending'
    ).first()
    
    if vibe:
        vibe.status = 'accepted'
        db.session.commit()
        flash(f"You matched with {sender_username}!")
    
    return redirect(url_for('dashboard'))

@app.route('/deny-vibe/<sender_username>', methods=['POST'])
def deny_vibe(sender_username):
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('landing'))
    
    vibe = Vibe.query.filter_by(
        sender=sender_username, 
        receiver=user.reddit_username, 
        status='pending'
    ).first()
    
    if vibe:
        vibe.status = 'denied'
        db.session.commit()
        flash(f"Vibe from {sender_username} denied.")
    
    return redirect(url_for('dashboard'))

@app.route('/unmatch/<username>', methods=['POST'])
def unmatch(username):
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('landing'))
    
    # Delete all vibes between the two users
    Vibe.query.filter(
        ((Vibe.sender == user.reddit_username) & (Vibe.receiver == username)) |
        ((Vibe.sender == username) & (Vibe.receiver == user.reddit_username))
    ).delete()
    
    db.session.commit()
    flash(f"Unmatched with {username}.")
    
    return redirect(url_for('dashboard'))

# ---------------------- 📬 Messaging & Sharing ----------------------

@app.route('/message/<username>')
def message_user(username):
    if 'user_id' not in session:
        return redirect(url_for('landing'))
    
    return redirect(f"https://www.reddit.com/message/compose/?to={username}")

@app.route('/share-profile/<username>')
def share_profile(username):
    user = User.query.filter_by(reddit_username=username).first()
    if not user:
        flash("User not found.")
        return redirect(url_for('dashboard'))
    
    return render_template('share_profile.html', user=user)

# ---------------------- 🛠️ Admin Panel ----------------------

@app.route('/admin')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('landing'))

    user = User.query.get(session['user_id'])
    if not user or user.reddit_username != ADMIN_USERNAME:
        flash("Access denied.")
        return redirect(url_for('dashboard'))

    ist = timezone('Asia/Kolkata')
    users = User.query.order_by(User.joined.desc()).all()
    for u in users:
        u.joined_ist = u.joined.replace(tzinfo=timezone('UTC')).astimezone(ist)
    
    return render_template('admin_dashboard.html', users=users)

@app.route('/admin/reports')
def admin_reports():
    if 'user_id' not in session:
        return redirect(url_for('landing'))

    user = User.query.get(session['user_id'])
    if not user or user.reddit_username != ADMIN_USERNAME:
        flash("Access denied.")
        return redirect(url_for('dashboard'))

    # Get some basic stats
    total_users = User.query.count()
    total_vibes = Vibe.query.count()
    pending_vibes = Vibe.query.filter_by(status='pending').count()
    accepted_vibes = Vibe.query.filter_by(status='accepted').count()
    
    stats = {
        'total_users': total_users,
        'total_vibes': total_vibes,
        'pending_vibes': pending_vibes,
        'accepted_vibes': accepted_vibes
    }
    
    return render_template('reports.html', stats=stats)

@app.route('/admin/ban/<username>')
def admin_ban(username):
    if 'user_id' not in session:
        return redirect(url_for('landing'))

    user = User.query.get(session['user_id'])
    if not user or user.reddit_username != ADMIN_USERNAME:
        flash("Access denied.")
        return redirect(url_for('dashboard'))

    target_user = User.query.filter_by(reddit_username=username).first()
    if target_user:
        target_user.is_banned = not target_user.is_banned
        db.session.commit()
        status = "banned" if target_user.is_banned else "unbanned"
        flash(f"User {username} has been {status}.")
    else:
        flash("User not found.")
    
    return redirect(url_for('admin_panel'))

# ---------------------- Error Handlers ----------------------

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500
    

## Issue 1: Database Connection/Migration
# The most likely cause is database issues. Add this to check:

@app.route('/debug')
def debug_route():
    """Temporary debug route to check database connectivity"""
    try:
        # Test database connection
        user_count = User.query.count()
        vibe_count = Vibe.query.count()
        
        return f"""
        <h2>Debug Info:</h2>
        <p>Database connected: ✅</p>
        <p>Total users: {user_count}</p>
        <p>Total vibes: {vibe_count}</p>
        <p>Session data: {dict(session)}</p>
        <p>Environment variables:</p>
        <ul>
            <li>DATABASE_URL: {'✅' if os.getenv('DATABASE_URL') else '❌'}</li>
            <li>SECRET_KEY: {'✅' if os.getenv('SECRET_KEY') else '❌'}</li>
            <li>REDDIT_CLIENT_ID: {'✅' if os.getenv('REDDIT_CLIENT_ID') else '❌'}</li>
            <li>REDDIT_CLIENT_SECRET: {'✅' if os.getenv('REDDIT_CLIENT_SECRET') else '❌'}</li>
            <li>REDIRECT_URI: {os.getenv('REDIRECT_URI', 'Not set')}</li>
        </ul>
        """
    except Exception as e:
        return f"Database error: {str(e)}"

@app.route('/init-db')
def init_db():
    """Initialize database tables - use once then remove"""
    try:
        db.create_all()
        return "Database tables created successfully!"
    except Exception as e:
        return f"Error creating tables: {e}"
# ---------------------- Run Server ----------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=False)
