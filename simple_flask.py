#!/usr/bin/env python3
"""
간단한 Flask 서버 (Flask-WTF 없이)
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
import ipaddress
from config import ALLOWED_IPS, ADMIN_USERNAME, ADMIN_PASSWORD, HOST, PORT, DEBUG

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///budget_management.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

def is_allowed_ip(ip):
    """IP 주소가 허용된 대역에 속하는지 확인"""
    try:
        client_ip = ipaddress.ip_address(ip)
        return any(client_ip in network for network in ALLOWED_IPS)
    except:
        return False

# @app.before_request
# def check_ip():
#     """모든 요청에 대해 IP 제한 확인"""
#     if request.remote_addr and not is_allowed_ip(request.remote_addr):
#         return "접근이 제한된 IP 주소입니다.", 403

# 데이터베이스 모델
class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    leader_name = db.Column(db.String(100), nullable=True)
    department_budget = db.Column(db.Integer, nullable=False)
    student_budget = db.Column(db.Integer, nullable=False)
    
    def __repr__(self):
        return f'<Team {self.name}>'

class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    item_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    estimated_cost = db.Column(db.Integer, nullable=False)
    link = db.Column(db.String(500), nullable=False)
    store = db.Column(db.String(100), nullable=False)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    team = db.relationship('Team', backref=db.backref('purchases', lazy=True))
    
    def __repr__(self):
        return f'<Purchase {self.item_name}>'

class OtherRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    team = db.relationship('Team', backref=db.backref('other_requests', lazy=True))
    
    def __repr__(self):
        return f'<OtherRequest {self.id}>'

# 라우트
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'purchase_submit' in request.form:
            # 구매내역 업로드 처리
            team_name = request.form.get('team_name')
            leader_name = request.form.get('leader_name')
            item_name = request.form.get('item_name')
            quantity = int(request.form.get('quantity'))
            estimated_cost = int(request.form.get('estimated_cost'))
            link = request.form.get('link')
            store = request.form.get('store')
            
            team = Team.query.filter_by(name=team_name).first()
            if team and team.leader_name == leader_name:
                purchase = Purchase(
                    team_id=team.id,
                    item_name=item_name,
                    quantity=quantity,
                    estimated_cost=estimated_cost,
                    link=link,
                    store=store
                )
                db.session.add(purchase)
                db.session.commit()
                flash('구매내역이 성공적으로 업로드되었습니다.', 'success')
                return redirect(url_for('upload'))
            else:
                flash('조장 이름이 일치하지 않습니다.', 'error')
        
        elif 'other_submit' in request.form:
            # 기타 구매 요청 처리
            team_name = request.form.get('other_team_name')
            leader_name = request.form.get('other_leader_name')
            content = request.form.get('content')
            
            team = Team.query.filter_by(name=team_name).first()
            if team and team.leader_name == leader_name:
                other_request = OtherRequest(
                    team_id=team.id,
                    content=content
                )
                db.session.add(other_request)
                db.session.commit()
                flash('기타 구매 요청이 성공적으로 제출되었습니다.', 'success')
                return redirect(url_for('upload'))
            else:
                flash('조장 이름이 일치하지 않습니다.', 'error')
    
    teams = Team.query.all()
    return render_template('upload.html', teams=teams)

@app.route('/check_balance', methods=['GET', 'POST'])
def check_balance():
    balance_info = None
    
    if request.method == 'POST':
        team_name = request.form.get('team_name')
        leader_name = request.form.get('leader_name')
        
        team = Team.query.filter_by(name=team_name).first()
        if team and team.leader_name == leader_name:
            approved_purchases = Purchase.query.filter_by(team_id=team.id, is_approved=True).all()
            total_department_spent = sum(p.estimated_cost for p in approved_purchases)
            total_student_spent = sum(p.estimated_cost for p in approved_purchases)
            
            balance_info = {
                'team_name': team.name,
                'leader_name': team.leader_name,
                'department_budget': team.department_budget,
                'student_budget': team.student_budget,
                'department_remaining': team.department_budget - total_department_spent,
                'student_remaining': team.student_budget - total_student_spent
            }
        else:
            flash('조장 이름이 일치하지 않습니다.', 'error')
    
    teams = Team.query.all()
    return render_template('check_balance.html', teams=teams, balance_info=balance_info)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'admin_logged_in' not in session:
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                session['admin_logged_in'] = True
                flash('관리자로 로그인되었습니다.', 'success')
                return redirect(url_for('admin'))
            else:
                flash('아이디 또는 비밀번호가 올바르지 않습니다.', 'error')
        
        return render_template('admin_login.html')
    
    # 관리자 로그인 후
    if request.method == 'POST' and 'leader_update' in request.form:
        team_name = request.form.get('leader_team_name')
        leader_name = request.form.get('leader_name')
        
        team = Team.query.filter_by(name=team_name).first()
        if team:
            team.leader_name = leader_name
            db.session.commit()
            flash('조장 정보가 업데이트되었습니다.', 'success')
            return redirect(url_for('admin'))
    
    teams = Team.query.all()
    all_teams_info = []
    for team in teams:
        approved_purchases = Purchase.query.filter_by(team_id=team.id, is_approved=True).all()
        total_spent = sum(p.estimated_cost for p in approved_purchases)
        
        all_teams_info.append({
            'team_name': team.name,
            'leader_name': team.leader_name,
            'department_budget': team.department_budget,
            'student_budget': team.student_budget,
            'total_budget': team.department_budget + team.student_budget,
            'total_spent': total_spent,
            'remaining': (team.department_budget + team.student_budget) - total_spent
        })
    
    pending_purchases = Purchase.query.filter_by(is_approved=False).all()
    other_requests = OtherRequest.query.all()
    
    return render_template('admin.html', 
                         teams=teams,
                         all_teams_info=all_teams_info,
                         pending_purchases=pending_purchases,
                         other_requests=other_requests)

@app.route('/approve_purchase/<int:purchase_id>')
def approve_purchase(purchase_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    purchase = Purchase.query.get_or_404(purchase_id)
    purchase.is_approved = True
    db.session.commit()
    flash('구매내역이 승인되었습니다.', 'success')
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('index'))

def init_db():
    """데이터베이스 초기화 및 초기 데이터 설정"""
    with app.app_context():
        db.create_all()
        
        teams_data = [
            {'name': '월요일 1조', 'department_budget': 600000, 'student_budget': 500000},
            {'name': '월요일 2조', 'department_budget': 700000, 'student_budget': 500000},
            {'name': '월요일 3조', 'department_budget': 600000, 'student_budget': 500000},
            {'name': '월요일 4조', 'department_budget': 700000, 'student_budget': 500000},
            {'name': '화요일 1조', 'department_budget': 600000, 'student_budget': 500000},
            {'name': '화요일 2조', 'department_budget': 700000, 'student_budget': 500000},
            {'name': '화요일 3조', 'department_budget': 600000, 'student_budget': 500000},
            {'name': '화요일 4조', 'department_budget': 700000, 'student_budget': 500000},
            {'name': '화요일 5조', 'department_budget': 600000, 'student_budget': 500000},
            {'name': '화요일 6조', 'department_budget': 700000, 'student_budget': 500000},
            {'name': '화요일 7조', 'department_budget': 600000, 'student_budget': 500000},
        ]
        
        for team_data in teams_data:
            existing_team = Team.query.filter_by(name=team_data['name']).first()
            if not existing_team:
                team = Team(**team_data)
                db.session.add(team)
        
        db.session.commit()
        print("데이터베이스가 초기화되었습니다.")

if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("🎓 예산 관리 시스템 (Flask)이 시작되었습니다!")
    print("=" * 60)
    print(f"🌐 접속 주소: http://127.0.0.1:{PORT}")
    print(f"🌐 또는: http://localhost:{PORT}")
    print("=" * 60)
    print("✅ 모든 기능이 사용 가능합니다!")
    print("   - 구매내역 업로드")
    print("   - 조별 잔여금액 확인")
    print("   - 관리자 모드 (MSE3105 / KHU)")
    print("=" * 60)
    
    # Render 배포를 위한 포트 설정
    import os
    port = int(os.environ.get('PORT', PORT))
    app.run(debug=DEBUG, host='0.0.0.0', port=port)
