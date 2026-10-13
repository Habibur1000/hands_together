import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Donation

app = Flask(__name__)
app.config['SECRET_KEY'] = 'handstogether2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hands_together.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'register'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        email = request.form['email']
        gender = request.form['gender']
        role = request.form['role']
        password = request.form['password']
        confirm = request.form['confirm']

        if password != confirm:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('This email is already registered', 'error')
            return redirect(url_for('register'))

        hashed = generate_password_hash(password)
        new_user = User(name=name, phone=phone, email=email, gender=gender, role=role, password_hash=hashed)
        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully. Please sign in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Wrong email or password', 'error')

    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    my_donations = Donation.query.filter_by(donor_id=current_user.id).count()
    total_donations = Donation.query.count()
    return render_template('dashboard.html', user=current_user, my_donations=my_donations, total_donations=total_donations)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/donate', methods=['GET', 'POST'])
@login_required
def donate():
    if request.method == 'POST':
        title = request.form['title']
        category = request.form['category']
        condition = request.form['condition']
        description = request.form['description']
        location = request.form['location']

        photo_filename = None
        file = request.files.get('photo')

        if file and file.filename:
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp_prefix = str(int(db.func.strftime('%s', 'now').expr if False else __import__('time').time()))
                filename = f"{timestamp_prefix}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                photo_filename = filename
            else:
                flash('Only image files are allowed (jpg, png, gif, webp)', 'error')
                return redirect(url_for('donate'))

        new_donation = Donation(
            title=title,
            category=category,
            condition=condition,
            description=description,
            location=location,
            photo_filename=photo_filename,
            donor_id=current_user.id
        )
        db.session.add(new_donation)
        db.session.commit()

        flash('Your donation has been posted', 'success')
        return redirect(url_for('donations'))

    return render_template('donate.html')

@app.route('/donations')
def donations():
    search = request.args.get('search', '')
    category = request.args.get('category', '')

    query = Donation.query

    if search:
        query = query.filter(
            db.or_(
                Donation.title.ilike(f'%{search}%'),
                Donation.description.ilike(f'%{search}%'),
                Donation.location.ilike(f'%{search}%')
            )
        )

    if category:
        query = query.filter_by(category=category)

    all_donations = query.order_by(Donation.posted_at.desc()).all()

    return render_template('donations.html', donations=all_donations, search=search, category=category)

@app.route('/donation/<int:donation_id>')
@login_required
def donation_detail(donation_id):
    donation = Donation.query.get_or_404(donation_id)
    return render_template('donation_detail.html', donation=donation)

@app.route('/donation/<int:donation_id>/delete')
@login_required
def delete_donation(donation_id):
    donation = Donation.query.get_or_404(donation_id)
    if donation.donor_id != current_user.id:
        flash('You can only delete your own donations', 'error')
        return redirect(url_for('donations'))

    if donation.photo_filename:
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], donation.photo_filename)
        if os.path.exists(photo_path):
            os.remove(photo_path)

    db.session.delete(donation)
    db.session.commit()
    flash('Donation removed', 'success')
    return redirect(url_for('donations'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)