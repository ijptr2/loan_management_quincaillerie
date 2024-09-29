
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pandas as pd
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///loan_management.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    business_name = db.Column(db.String(100), nullable=False)

class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    date_taken = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    remaining_amount = db.Column(db.Float, nullable=False)
    client = db.relationship('Client', backref=db.backref('loans', lazy=True))

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey('loan.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit=db.Column(db.String(50),nullable=False)
    price = db.Column(db.Float, nullable=False)
    loan = db.relationship('Loan', backref=db.backref('items', lazy=True))

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey('loan.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    method=db.Column(db.String(100),nullable=False)
    removed=db.Column(db.String(100),nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    loan = db.relationship('Loan', backref=db.backref('payments', lazy=True))

with app.app_context():
    #db.drop_all()
    db.create_all()   

# Get the Desktop path for the current user
desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')

# Define the folder path where the Excel file will be saved
folder_path = os.path.join(desktop_path, 'loan_exports')

with app.app_context():
    # Check if the folder exists, and create it if not
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"Folder '{folder_path}' created successfully.")


    loans = Loan.query.all()

    # Prepare data for DataFrame
    loan_data=[]
    for loan in loans:
        for payment in loan.payments:
            for item in loan.items:  # Loop through all items related to the loan
                loan_data.append({
                    'Loan ID': loan.id,
                    'Client Name': loan.client.name,
                    'Phone Number': loan.client.phone_number,
                    'Business Name': loan.client.business_name,
                    'Total Loan Amount': loan.total_amount,
                    'Remaining Loan Amount': loan.remaining_amount,
                    'Payment Amount': payment.amount,
                    'Payment Method': payment.method,
                    'Payment Date': payment.date,
                    'Processed By':payment.removed,
                    'Item Name': item.name,
                    'Item Quantity': item.quantity,
                    'Item Price': item.price
                })

    # Convert to a DataFrame
    df = pd.DataFrame(loan_data)

     # Define the path to save the Excel file
    excel_file_path = os.path.join(folder_path, 'loan_export_with_items.xlsx')

    # Save the DataFrame to an Excel file
    df.to_excel(excel_file_path, index=False)
    print(f"Data exported successfully to '{excel_file_path}'!")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    loans = Loan.query.all()
    return render_template('dashboard.html', loans=loans)

@app.route('/register_loan', methods=['GET', 'POST'])
@login_required
def register_loan():
    if request.method == 'POST':
        client_name = request.form['client_name']
        phone_number = request.form['phone_number']
        business_name = request.form['business_name']
        
        client = Client(name=client_name, phone_number=phone_number, business_name=business_name)
        db.session.add(client)
        db.session.commit()
        
        loan = Loan(client_id=client.id, total_amount=0, remaining_amount=0)
        db.session.add(loan)
        db.session.commit()
        
        items = request.form.getlist('item_name[]')
        units=request.form.getlist('item_unit[]')
        quantities = request.form.getlist('item_quantity[]')
        prices = request.form.getlist('item_price[]')
        
        total_amount = 0
        for item_name,unit_name, quantity, price in zip(items,units, quantities, prices):
            item = Item(loan_id=loan.id, name=item_name,quantity=int(quantity),unit=unit_name, price=float(price))
            db.session.add(item)
            total_amount += int(quantity) * float(price)
        
        loan.total_amount = total_amount
        loan.remaining_amount = total_amount
        db.session.commit()
        
        flash('Loan registered successfully', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('register_loan.html')

@app.route('/view_loan/<int:loan_id>')
@login_required
def view_loan(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    return render_template('view_loan.html', loan=loan)

@app.route('/make_payment/<int:loan_id>', methods=['GET', 'POST'])
@login_required
def make_payment(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    if request.method == 'POST':
        amount = float(request.form['amount'])
        method=request.form['payment_method']
        removed=request.form['removed_by']
        if amount > loan.remaining_amount:
            flash('Payment amount exceeds remaining loan balance', 'error')
        else:
            payment = Payment(loan_id=loan.id, amount=amount,method=method,removed=removed)
            loan.remaining_amount -= amount
            db.session.add(payment)
            db.session.commit()
            flash('Payment recorded successfully', 'success')
        return redirect(url_for('view_loan', loan_id=loan.id))
    return render_template('make_payment.html', loan=loan)



    




if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)