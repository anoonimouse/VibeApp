# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

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
    status = db.Column(db.String(20))  # pending, accepted, denied
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
