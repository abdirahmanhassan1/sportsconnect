from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sportconnect.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# Models

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text)
    location = db.Column(db.String(100))
    profile_pic = db.Column(db.String(255), default='default.jpg')

    posts = db.relationship('Post', backref='user', lazy=True)
    events = db.relationship('Event', backref='creator', lazy=True)
    followers = db.relationship(
        'Follow', foreign_keys='Follow.followed_id', backref='followed', lazy='dynamic')
    following = db.relationship(
        'Follow', foreign_keys='Follow.follower_id', backref='follower', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    likes = db.relationship('Like', backref='post', lazy=True)


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    date = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    sport = db.Column(db.String(50), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    attendees = db.relationship('UserEvent', backref='event', lazy=True)


class UserEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'))


class Community(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sport = db.Column(db.String(50), nullable=False)
    emoji = db.Column(db.String(10), default='🏅')
    members = db.relationship('UserCommunity', backref='community', lazy=True)


class UserCommunity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    comm_id = db.Column(db.Integer, db.ForeignKey('community.id'))


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


# User loader

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Database initialization with sample data

def init_db():
    db.create_all()

    if not Community.query.first():
        communities = [
            Community(name="Hoops Hype", sport="Basketball", emoji="🏀"),
            Community(name="Trailblazers Run Club",
                      sport="Running", emoji="🏃‍♂️"),
            Community(name="Urban Cyclists", sport="Cycling", emoji="🚴‍♀️"),
            Community(name="Volleyball Vibes", sport="Volleyball", emoji="🏐"),
            Community(name="Tennis Titans", sport="Tennis", emoji="🎾"),
            Community(name="Swim Squad", sport="Swimming", emoji="🏊‍♂️"),
        ]
        db.session.bulk_save_objects(communities)
        db.session.commit()


# Routes

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('feed'))
    return redirect(url_for('login'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('signup'))
        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Account created. Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('feed'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('feed'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/feed', methods=['GET', 'POST'])
@login_required
def feed():
    if request.method == 'POST':
        content = request.form['content']
        image = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                filename = secure_filename(
                    f"post_{current_user.id}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image = filename
        post = Post(content=content, image=image, user_id=current_user.id)
        db.session.add(post)
        db.session.commit()
        flash('Posted!', 'success')
    posts = Post.query.options(db.joinedload(Post.user)).order_by(
        Post.created_at.desc()).all()
    events = Event.query.order_by(Event.date).all()
    return render_template('feed.html', posts=posts, events=events)


@app.route('/like_post/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(
        user_id=current_user.id, post_id=post_id).first()
    if like:
        db.session.delete(like)
        db.session.commit()
        return jsonify({'liked': False, 'likes_count': len(post.likes)})
    new_like = Like(user_id=current_user.id, post_id=post_id)
    db.session.add(new_like)
    db.session.commit()
    return jsonify({'liked': True, 'likes_count': len(post.likes)})


@app.route('/events', methods=['GET', 'POST'])
@login_required
def events():
    if request.method == 'POST':
        event = Event(
            title=request.form['title'],
            date=request.form['date'],
            location=request.form['location'],
            sport=request.form['sport'],
            creator_id=current_user.id
        )
        db.session.add(event)
        db.session.commit()
        flash('Event created!', 'success')
    events = Event.query.order_by(Event.date).all()
    return render_template('events.html', events=events)


@app.route('/join_event/<int:event_id>')
@login_required
def join_event(event_id):
    event = Event.query.get_or_404(event_id)
    if not UserEvent.query.filter_by(user_id=current_user.id, event_id=event_id).first():
        ue = UserEvent(user_id=current_user.id, event_id=event_id)
        db.session.add(ue)
        db.session.commit()
        flash(f'Joined event {event.title}!', 'success')
    else:
        flash('Already joined!', 'warning')
    return redirect(url_for('events'))


@app.route('/communities')
@login_required
def communities():
    search_query = request.args.get('q', '')
    if search_query:
        communities = Community.query.filter(
            (Community.name.ilike(f'%{search_query}%')) |
            (Community.sport.ilike(f'%{search_query}%'))
        ).all()
    else:
        communities = Community.query.all()
    joined_comm_ids = [uc.comm_id for uc in UserCommunity.query.filter_by(
        user_id=current_user.id).all()]
    return render_template('communities.html', communities=communities, joined=joined_comm_ids, search_query=search_query)


@app.route('/join_community/<int:comm_id>')
@login_required
def join_community(comm_id):
    community = Community.query.get_or_404(comm_id)
    if not UserCommunity.query.filter_by(user_id=current_user.id, comm_id=comm_id).first():
        uc = UserCommunity(user_id=current_user.id, comm_id=comm_id)
        db.session.add(uc)
        db.session.commit()
        flash(f'Joined community {community.name}!', 'success')
    else:
        flash('Already a member!', 'warning')
    return redirect(url_for('communities'))


@app.route('/messages')
@login_required
def messages():
    search_term = request.args.get('q', '')
    query_users = User.query.filter(User.id != current_user.id)
    if search_term:
        query_users = query_users.filter(User.name.ilike(f'%{search_term}%'))
    users = query_users.all()
    return render_template('messages.html', users=users, search_term=search_term)


@app.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    user = User.query.get_or_404(user_id)
    post_count = Post.query.filter_by(user_id=user.id).count()
    event_count = UserEvent.query.filter_by(user_id=user.id).count()
    follower_count = user.followers.count()
    following_count = user.following.count()
    is_following = False
    if user.id != current_user.id:
        is_following = Follow.query.filter_by(
            follower_id=current_user.id, followed_id=user.id).first() is not None
    return render_template('profile.html', user=user, post_count=post_count, event_count=event_count,
                           follower_count=follower_count, following_count=following_count, is_following=is_following)


@app.route('/profile', methods=['GET'])
@login_required
def current_profile():
    return redirect(url_for('profile', user_id=current_user.id))


@app.route('/profile_edit/<int:user_id>', methods=['POST'])
@login_required
def edit_profile(user_id):
    if current_user.id != user_id:
        abort(403)
    user = User.query.get_or_404(user_id)
    user.name = request.form.get('name')
    user.bio = request.form.get('bio')
    user.location = request.form.get('location')
    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        if file and file.filename != '':
            filename = secure_filename(f"{user.id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            user.profile_pic = filename
    db.session.commit()
    flash('Profile updated!', 'success')
    return redirect(url_for('profile', user_id=user_id))


@app.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow(user_id):
    if user_id == current_user.id:
        flash("You can't follow yourself.", "warning")
        return redirect(url_for('profile', user_id=user_id))
    user_to_follow = User.query.get_or_404(user_id)
    if not Follow.query.filter_by(follower_id=current_user.id, followed_id=user_id).first():
        follow = Follow(follower_id=current_user.id, followed_id=user_id)
        db.session.add(follow)
        db.session.commit()
        flash(f'You are now following {user_to_follow.name}', 'success')
    else:
        flash('Already following', 'info')
    return redirect(url_for('profile', user_id=user_id))


@app.route('/chat/<int:user_id>', methods=['GET', 'POST'])
@login_required
def chat(user_id):
    other_user = User.query.get_or_404(user_id)
    if other_user == current_user:
        flash("You cannot chat with yourself.", "warning")
        return redirect(url_for('messages'))

    if request.method == 'POST':
        content = request.form['content'].strip()
        if content:
            msg = Message(sender_id=current_user.id,
                          receiver_id=other_user.id, content=content)
            db.session.add(msg)
            db.session.commit()
            flash('Message sent!', 'success')
        return redirect(url_for('chat', user_id=user_id))

    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == other_user.id)) |
        ((Message.sender_id == other_user.id) &
         (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    return render_template('chat.html', other_user=other_user, messages=messages)


@app.route('/unfollow/<int:user_id>', methods=['POST'])
@login_required
def unfollow(user_id):
    follow = Follow.query.filter_by(
        follower_id=current_user.id, followed_id=user_id).first()
    if follow:
        db.session.delete(follow)
        db.session.commit()
        flash('Unfollowed', 'success')
    return redirect(url_for('profile', user_id=user_id))


# Serve uploaded files

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return app.send_static_file(os.path.join('uploads', filename))


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, host='127.0.0.1', port=5003)
