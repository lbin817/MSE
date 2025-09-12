#!/usr/bin/env python3
"""
간단한 Flask 서버 (Flask-WTF 없이)
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
import os
import json
from datetime import datetime
import ipaddress
from werkzeug.utils import secure_filename
import uuid
import io
import csv
import requests
from config import ALLOWED_IPS, ADMIN_USERNAME, ADMIN_PASSWORD, HOST, PORT, DEBUG

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# 데이터베이스 설정 - 모든 환경에서 SQLite 사용
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'budget_management.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
print(f"💾 SQLite 데이터베이스 사용: {db_path}")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 파일 업로드 설정
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB 제한 (견적서용)

# 업로드 폴더 생성
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# JSON 백업 폴더 생성
JSON_BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'json_backup')
if not os.path.exists(JSON_BACKUP_DIR):
    os.makedirs(JSON_BACKUP_DIR)

db = SQLAlchemy(app)

def is_allowed_ip(ip):
    """IP 주소가 허용된 대역에 속하는지 확인"""
    try:
        client_ip = ipaddress.ip_address(ip)
        return any(client_ip in network for network in ALLOWED_IPS)
    except:
        return False

def allowed_file(filename):
    """허용된 파일 확장자인지 확인"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# GitHub API 함수들
def upload_to_github(filename, content):
    """GitHub에 JSON 파일 업로드"""
    try:
        # GitHub API 토큰 (환경변수에서 가져오기)
        token = os.environ.get('GITHUB_TOKEN')
        if not token:
            print("❌ GitHub 토큰이 설정되지 않았습니다.")
            return False
        
        # GitHub API URL
        url = f"https://api.github.com/repos/lbin817/MSE/contents/json_backup/{filename}"
        
        # 기존 파일 정보 가져오기
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        response = requests.get(url, headers=headers)
        sha = None
        if response.status_code == 200:
            sha = response.json().get('sha')
        
        # 파일 업로드 (Base64 인코딩)
        import base64
        encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        data = {
            'message': f'Update {filename}',
            'content': encoded_content,
            'sha': sha
        }
        
        response = requests.put(url, headers=headers, json=data)
        
        if response.status_code in [200, 201]:
            print(f"✅ {filename} GitHub 업로드 성공!")
            return True
        else:
            print(f"❌ {filename} GitHub 업로드 실패: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ GitHub 업로드 오류: {e}")
        return False

def download_from_github(filename):
    """GitHub에서 JSON 파일 다운로드"""
    try:
        # GitHub API URL
        url = f"https://api.github.com/repos/lbin817/MSE/contents/json_backup/{filename}"
        
        headers = {
            'Accept': 'application/vnd.github.v3+json'
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            content = response.json().get('content', '')
            # Base64 디코딩
            import base64
            decoded_content = base64.b64decode(content).decode('utf-8')
            return decoded_content
        else:
            print(f"❌ {filename} GitHub 다운로드 실패: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ GitHub 다운로드 오류: {e}")
        return None

# JSON 백업 함수들
def backup_to_json():
    """데이터베이스 데이터를 JSON 파일로 백업"""
    try:
        print("🔄 JSON 백업 시작...")
        print(f"📁 백업 디렉토리: {JSON_BACKUP_DIR}")
        
        # 팀 데이터 백업
        teams = Team.query.all()
        teams_data = {
            "teams": [
                {
                    "id": team.id,
                    "name": team.name,
                    "leader_name": team.leader_name or "",
                    "department_budget": team.department_budget,
                    "student_budget": team.student_budget,
                    "original_department_budget": getattr(team, 'original_department_budget', team.department_budget),
                    "original_student_budget": getattr(team, 'original_student_budget', team.student_budget)
                }
                for team in teams
            ]
        }
        
        # 구매내역 백업
        purchases = Purchase.query.all()
        purchases_data = {
            "purchases": [
                {
                    "id": purchase.id,
                    "team_id": purchase.team_id,
                    "item_name": purchase.item_name,
                    "price": purchase.price,
                    "quantity": purchase.quantity,
                    "total_amount": purchase.total_amount,
                    "store": purchase.store,
                    "budget_type": getattr(purchase, 'budget_type', 'department'),
                    "notes": purchase.notes or "",
                    "attachment_filename": getattr(purchase, 'attachment_filename', None),
                    "request_date": purchase.request_date.strftime('%Y-%m-%d %H:%M:%S'),
                    "status": purchase.status,
                    "is_approved": purchase.is_approved
                }
                for purchase in purchases
            ]
        }
        
        # 다중 구매내역 백업
        multi_purchases = MultiPurchase.query.all()
        multi_purchases_data = {
            "multi_purchases": [
                {
                    "id": multi_purchase.id,
                    "team_id": multi_purchase.team_id,
                    "store": multi_purchase.store,
                    "budget_type": multi_purchase.budget_type,
                    "notes": multi_purchase.notes or "",
                    "total_amount": multi_purchase.total_amount,
                    "items": [
                        {
                            "id": item.id,
                            "item_name": item.item_name,
                            "unit_price": item.unit_price,
                            "quantity": item.quantity,
                            "total_amount": item.total_amount
                        }
                        for item in multi_purchase.items
                    ],
                    "request_date": multi_purchase.request_date.strftime('%Y-%m-%d %H:%M:%S'),
                    "status": multi_purchase.status,
                    "is_approved": multi_purchase.is_approved
                }
                for multi_purchase in multi_purchases
            ]
        }
        
        # 기타 요청 백업
        other_requests = OtherRequest.query.all()
        other_requests_data = {
            "other_requests": [
                {
                    "id": request.id,
                    "team_id": request.team_id,
                    "request_type": request.request_type,
                    "description": request.description,
                    "request_date": request.request_date.strftime('%Y-%m-%d %H:%M:%S'),
                    "status": request.status,
                    "is_approved": request.is_approved
                }
                for request in other_requests
            ]
        }
        
        # JSON 파일로 저장
        teams_file = os.path.join(JSON_BACKUP_DIR, 'teams.json')
        purchases_file = os.path.join(JSON_BACKUP_DIR, 'purchases.json')
        multi_purchases_file = os.path.join(JSON_BACKUP_DIR, 'multi_purchases.json')
        other_requests_file = os.path.join(JSON_BACKUP_DIR, 'other_requests.json')
        
        print(f"💾 팀 데이터 저장: {teams_file}")
        with open(teams_file, 'w', encoding='utf-8') as f:
            json.dump(teams_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 구매내역 저장: {purchases_file}")
        with open(purchases_file, 'w', encoding='utf-8') as f:
            json.dump(purchases_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 다중 구매내역 저장: {multi_purchases_file}")
        with open(multi_purchases_file, 'w', encoding='utf-8') as f:
            json.dump(multi_purchases_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 기타 요청 저장: {other_requests_file}")
        with open(other_requests_file, 'w', encoding='utf-8') as f:
            json.dump(other_requests_data, f, ensure_ascii=False, indent=2)
        
        print("✅ JSON 백업 완료!")
        
        # GitHub에도 업로드 (토큰이 있을 때만)
        print("🔄 GitHub에 백업 업로드...")
        github_token = os.environ.get('GITHUB_TOKEN')
        if github_token:
            for filename, data in [('teams.json', teams_data), ('purchases.json', purchases_data), 
                                  ('multi_purchases.json', multi_purchases_data), ('other_requests.json', other_requests_data)]:
                content = json.dumps(data, ensure_ascii=False, indent=2)
                upload_to_github(filename, content)
        else:
            print("⚠️ GitHub 토큰이 없어서 로컬 백업만 실행됩니다.")
        
        return True
        
    except Exception as e:
        print(f"❌ JSON 백업 오류: {e}")
        return False

def save_uploaded_file(file):
    """업로드된 파일을 안전하게 저장"""
    if file and allowed_file(file.filename):
        # 고유한 파일명 생성
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        return unique_filename
    return None

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
    department_budget = db.Column(db.Integer, nullable=False)  # 현재 남은 예산
    student_budget = db.Column(db.Integer, nullable=False)     # 현재 남은 예산
    original_department_budget = db.Column(db.Integer, nullable=False)  # 원래 설정된 예산
    original_student_budget = db.Column(db.Integer, nullable=False)     # 원래 설정된 예산
    
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
    budget_type = db.Column(db.String(50), nullable=True)  # 'department' 또는 'student'
    attachment_filename = db.Column(db.String(255), nullable=True)  # 첨부파일명
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

class MultiPurchase(db.Model):
    """다중 품목 구매 요청"""
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    store = db.Column(db.String(100), nullable=False)
    total_cost = db.Column(db.Integer, nullable=False)
    attachment_filename = db.Column(db.String(255), nullable=True)  # 견적서 첨부파일
    is_approved = db.Column(db.Boolean, default=False)
    budget_type = db.Column(db.String(50), nullable=True)  # 'department' 또는 'student'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    team = db.relationship('Team', backref=db.backref('multi_purchases', lazy=True))
    items = db.relationship('MultiPurchaseItem', backref='multi_purchase', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<MultiPurchase {self.id}>'

class MultiPurchaseItem(db.Model):
    """다중 품목 구매의 개별 품목"""
    id = db.Column(db.Integer, primary_key=True)
    multi_purchase_id = db.Column(db.Integer, db.ForeignKey('multi_purchase.id'), nullable=False)
    item_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Integer, nullable=False)
    
    def __repr__(self):
        return f'<MultiPurchaseItem {self.item_name}>'

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
            store = request.form.get('store')
            link = request.form.get('link', '')
            
            # 파일 업로드 처리
            attachment_filename = None
            if 'attachment' in request.files:
                file = request.files['attachment']
                if file and file.filename:
                    attachment_filename = save_uploaded_file(file)
                    if not attachment_filename:
                        flash('지원하지 않는 파일 형식입니다. (PDF, 이미지, 문서 파일만 가능)', 'error')
                        return redirect(url_for('upload'))
            
            team = Team.query.filter_by(name=team_name).first()
            if team and team.leader_name == leader_name:
                purchase = Purchase(
                    team_id=team.id,
                    item_name=item_name,
                    quantity=quantity,
                    estimated_cost=estimated_cost,
                    link=link,
                    store=store,
                    attachment_filename=attachment_filename
                )
                db.session.add(purchase)
                db.session.commit()
                
                # JSON 백업 실행
                print("=" * 50)
                print("🔄 구매내역 업로드 후 JSON 백업 시작!")
                print("=" * 50)
                backup_to_json()
                print("=" * 50)
                
                flash('구매내역이 성공적으로 업로드되었습니다.', 'success')
                return redirect(url_for('upload'))
            else:
                flash('조장 이름이 일치하지 않습니다.', 'error')
        
        elif 'multi_submit' in request.form:
            # 다중 품목 구매 요청 처리
            team_name = request.form.get('multi_team_name')
            leader_name = request.form.get('multi_leader_name')
            store = request.form.get('multi_store')
            
            # 파일 업로드 처리
            attachment_filename = None
            if 'multi_attachment' in request.files:
                file = request.files['multi_attachment']
                if file.filename:
                    attachment_filename = save_uploaded_file(file)
                    if not attachment_filename:
                        flash('지원하지 않는 파일 형식입니다. (PDF, 이미지, 문서 파일만 가능)', 'error')
                        return redirect(url_for('upload'))
            
            # 품목 데이터 수집
            item_names = request.form.getlist('multi_item_name[]')
            quantities = request.form.getlist('multi_quantity[]')
            unit_prices = request.form.getlist('multi_unit_price[]')
            
            # 유효성 검사
            if not item_names or not quantities or not unit_prices:
                flash('품목 정보를 입력해주세요.', 'error')
                return redirect(url_for('upload'))
            
            # 빈 항목 제거
            items_data = []
            total_cost = 0
            for i, (item_name, quantity, unit_price) in enumerate(zip(item_names, quantities, unit_prices)):
                if item_name.strip() and quantity.strip() and unit_price.strip():
                    try:
                        qty = int(quantity)
                        price = int(unit_price)
                        items_data.append({
                            'item_name': item_name.strip(),
                            'quantity': qty,
                            'unit_price': price
                        })
                        total_cost += qty * price
                    except ValueError:
                        flash('수량과 단가는 숫자로 입력해주세요.', 'error')
                        return redirect(url_for('upload'))
            
            if not items_data:
                flash('최소 하나의 품목을 입력해주세요.', 'error')
                return redirect(url_for('upload'))
            
            team = Team.query.filter_by(name=team_name).first()
            if team and team.leader_name == leader_name:
                # 다중 구매 요청 생성
                multi_purchase = MultiPurchase(
                    team_id=team.id,
                    store=store,
                    total_cost=total_cost,
                    attachment_filename=attachment_filename
                )
                db.session.add(multi_purchase)
                db.session.flush()  # ID 생성
                
                # 개별 품목들 추가
                for item_data in items_data:
                    item = MultiPurchaseItem(
                        multi_purchase_id=multi_purchase.id,
                        item_name=item_data['item_name'],
                        quantity=item_data['quantity'],
                        unit_price=item_data['unit_price']
                    )
                    db.session.add(item)
                
                db.session.commit()
                
                # JSON 백업 실행
                backup_to_json()
                
                flash(f'다중 품목 구매 요청이 성공적으로 제출되었습니다. (총 {len(items_data)}개 품목, {total_cost:,}원)', 'success')
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
                
                # JSON 백업 실행
                backup_to_json()
                
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
            approved_multi_purchases = MultiPurchase.query.filter_by(team_id=team.id, is_approved=True).all()
            
            total_department_spent = sum(p.estimated_cost for p in approved_purchases if p.budget_type == 'department')
            total_student_spent = sum(p.estimated_cost for p in approved_purchases if p.budget_type == 'student')
            
            # 다중 구매내역에서도 예산 차감액 계산
            total_department_spent += sum(mp.total_cost for mp in approved_multi_purchases if mp.budget_type == 'department')
            total_student_spent += sum(mp.total_cost for mp in approved_multi_purchases if mp.budget_type == 'student')
            
            balance_info = {
                'team_name': team.name,
                'leader_name': team.leader_name,
                'department_budget': team.department_budget,
                'student_budget': team.student_budget,
                'department_remaining': team.department_budget - total_department_spent,
                'student_remaining': team.student_budget - total_student_spent,
                'purchases': approved_purchases,
                'multi_purchases': approved_multi_purchases
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
    
    # 예산 설정 처리
    if request.method == 'POST' and 'budget_update' in request.form:
        team_name = request.form.get('budget_team_name')
        try:
            department_budget = int(request.form.get('department_budget'))
            student_budget = int(request.form.get('student_budget'))
            
            # 유효성 검사
            if department_budget < 0 or student_budget < 0:
                flash('예산은 0원 이상이어야 합니다.', 'error')
                return redirect(url_for('admin'))
            
            if department_budget > 10000000 or student_budget > 10000000:
                flash('예산은 1천만원을 초과할 수 없습니다.', 'error')
                return redirect(url_for('admin'))
            
            team = Team.query.filter_by(name=team_name).first()
            if team:
                team.department_budget = department_budget
                team.student_budget = student_budget
                team.original_department_budget = department_budget
                team.original_student_budget = student_budget
                db.session.commit()
                flash(f'{team_name}의 예산이 업데이트되었습니다. (학과지원: {department_budget:,}원, 학생지원: {student_budget:,}원)', 'success')
                return redirect(url_for('admin'))
            else:
                flash('선택한 조를 찾을 수 없습니다.', 'error')
                return redirect(url_for('admin'))
        except ValueError:
            flash('예산은 숫자로 입력해주세요.', 'error')
            return redirect(url_for('admin'))
    
    teams = Team.query.all()
    all_teams_info = []
    for team in teams:
        approved_purchases = Purchase.query.filter_by(team_id=team.id, is_approved=True).all()
        approved_multi_purchases = MultiPurchase.query.filter_by(team_id=team.id, is_approved=True).all()
        
        # 일반 구매내역과 다중 구매내역 모두 포함
        total_spent = sum(p.estimated_cost for p in approved_purchases)
        total_spent += sum(mp.total_cost for mp in approved_multi_purchases)
        
        all_teams_info.append({
            'team_name': team.name,
            'leader_name': team.leader_name,
            'department_budget': team.department_budget,
            'student_budget': team.student_budget,
            'total_budget': team.original_department_budget + team.original_student_budget,  # 원래 예산 사용
            'total_spent': total_spent,
            'remaining': (team.original_department_budget + team.original_student_budget) - total_spent  # 원래 예산에서 사용액 차감
        })
    
    pending_purchases = Purchase.query.filter_by(is_approved=False).all()
    all_purchases = Purchase.query.order_by(Purchase.created_at.desc()).all()
    pending_multi_purchases = MultiPurchase.query.filter_by(is_approved=False).all()
    all_multi_purchases = MultiPurchase.query.order_by(MultiPurchase.created_at.desc()).all()
    other_requests = OtherRequest.query.all()
    
    return render_template('admin.html', 
                         teams=teams,
                         all_teams_info=all_teams_info,
                         pending_purchases=pending_purchases,
                         all_purchases=all_purchases,
                         pending_multi_purchases=pending_multi_purchases,
                         all_multi_purchases=all_multi_purchases,
                         other_requests=other_requests)

@app.route('/approve_purchase/<int:purchase_id>', methods=['POST'])
def approve_purchase(purchase_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    purchase = Purchase.query.get_or_404(purchase_id)
    budget_type = request.form.get('budget_type')
    
    if not budget_type:
        flash('예산 유형을 선택해주세요.', 'error')
        return redirect(url_for('admin'))
    
    # 예산 차감
    team = purchase.team
    if budget_type == 'department':
        if team.department_budget >= purchase.estimated_cost:
            team.department_budget -= purchase.estimated_cost
            purchase.budget_type = 'department'
        else:
            flash('학과지원사업 예산이 부족합니다.', 'error')
            return redirect(url_for('admin'))
    elif budget_type == 'student':
        if team.student_budget >= purchase.estimated_cost:
            team.student_budget -= purchase.estimated_cost
            purchase.budget_type = 'student'
        else:
            flash('학생지원사업 예산이 부족합니다.', 'error')
            return redirect(url_for('admin'))
    
    purchase.is_approved = True
    db.session.commit()
    
    # JSON 백업 실행
    backup_to_json()
    
    flash('구매내역이 승인되었습니다.', 'success')
    return redirect(url_for('admin'))

@app.route('/cancel_approval/<int:purchase_id>')
def cancel_approval(purchase_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    purchase = Purchase.query.get_or_404(purchase_id)
    if not purchase.is_approved:
        flash('이미 승인되지 않은 구매내역입니다.', 'error')
        return redirect(url_for('admin'))
    
    # 예산 복구
    team = purchase.team
    if purchase.budget_type == 'department':
        team.department_budget += purchase.estimated_cost
    elif purchase.budget_type == 'student':
        team.student_budget += purchase.estimated_cost
    
    purchase.is_approved = False
    purchase.budget_type = None
    db.session.commit()
    
    # JSON 백업 실행
    backup_to_json()
    
    flash('구매 승인이 취소되었습니다.', 'success')
    return redirect(url_for('admin'))

@app.route('/delete_purchase/<int:purchase_id>')
def delete_purchase(purchase_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    purchase = Purchase.query.get_or_404(purchase_id)
    
    # 승인된 구매내역인 경우 예산 복구
    if purchase.is_approved:
        team = purchase.team
        if purchase.budget_type == 'department':
            team.department_budget += purchase.estimated_cost
        elif purchase.budget_type == 'student':
            team.student_budget += purchase.estimated_cost
    
    # 구매내역 삭제
    db.session.delete(purchase)
    db.session.commit()
    flash('구매내역이 삭제되었습니다.', 'success')
    return redirect(url_for('admin'))

@app.route('/approve_multi_purchase/<int:multi_purchase_id>', methods=['POST'])
def approve_multi_purchase(multi_purchase_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    multi_purchase = MultiPurchase.query.get_or_404(multi_purchase_id)
    budget_type = request.form.get('budget_type')
    
    if not budget_type:
        flash('예산 유형을 선택해주세요.', 'error')
        return redirect(url_for('admin'))
    
    # 예산 차감
    team = multi_purchase.team
    if budget_type == 'department':
        if team.department_budget >= multi_purchase.total_cost:
            team.department_budget -= multi_purchase.total_cost
            multi_purchase.budget_type = 'department'
        else:
            flash('학과지원사업 예산이 부족합니다.', 'error')
            return redirect(url_for('admin'))
    elif budget_type == 'student':
        if team.student_budget >= multi_purchase.total_cost:
            team.student_budget -= multi_purchase.total_cost
            multi_purchase.budget_type = 'student'
        else:
            flash('학생지원사업 예산이 부족합니다.', 'error')
            return redirect(url_for('admin'))
    
    multi_purchase.is_approved = True
    db.session.commit()
    flash('다중 품목 구매내역이 승인되었습니다.', 'success')
    return redirect(url_for('admin'))

@app.route('/cancel_multi_approval/<int:multi_purchase_id>')
def cancel_multi_approval(multi_purchase_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    multi_purchase = MultiPurchase.query.get_or_404(multi_purchase_id)
    if not multi_purchase.is_approved:
        flash('이미 승인되지 않은 구매내역입니다.', 'error')
        return redirect(url_for('admin'))
    
    # 예산 복구
    team = multi_purchase.team
    if multi_purchase.budget_type == 'department':
        team.department_budget += multi_purchase.total_cost
    elif multi_purchase.budget_type == 'student':
        team.student_budget += multi_purchase.total_cost
    
    multi_purchase.is_approved = False
    multi_purchase.budget_type = None
    db.session.commit()
    flash('다중 품목 구매 승인이 취소되었습니다.', 'success')
    return redirect(url_for('admin'))

@app.route('/delete_multi_purchase/<int:multi_purchase_id>')
def delete_multi_purchase(multi_purchase_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    multi_purchase = MultiPurchase.query.get_or_404(multi_purchase_id)
    
    # 승인된 구매내역인 경우 예산 복구
    if multi_purchase.is_approved:
        team = multi_purchase.team
        if multi_purchase.budget_type == 'department':
            team.department_budget += multi_purchase.total_cost
        elif multi_purchase.budget_type == 'student':
            team.student_budget += multi_purchase.total_cost
    
    # 구매내역 삭제 (관련 품목들도 자동 삭제됨)
    db.session.delete(multi_purchase)
    db.session.commit()
    flash('다중 품목 구매내역이 삭제되었습니다.', 'success')
    return redirect(url_for('admin'))

@app.route('/download/<filename>')
def download_file(filename):
    """첨부파일 다운로드"""
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            flash('파일을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin'))
    except Exception as e:
        flash('파일 다운로드 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin'))

@app.route('/export_excel')
def export_excel():
    """전체 구매내역을 엑셀(CSV)로 다운로드"""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    try:
        # Tab 구분 텍스트 파일 생성
        txt_content = ""
        
        # 헤더 작성
        headers = ['ID', '조 번호', '조장', '품목명', '수량', '예상비용', '쇼핑몰', '예산유형', '상태', '요청일시', '견적서첨부']
        txt_content += '\t'.join(headers) + '\n'
        
        # 일반 구매내역
        purchases = Purchase.query.order_by(Purchase.created_at.desc()).all()
        for purchase in purchases:
            row = [
                str(purchase.id),
                purchase.team.name,
                purchase.team.leader_name or '미설정',
                purchase.item_name,
                str(purchase.quantity),
                str(purchase.estimated_cost),
                purchase.store,
                '학과지원사업' if getattr(purchase, 'budget_type', None) == 'department' else '학생지원사업' if getattr(purchase, 'budget_type', None) == 'student' else '미선택',
                '승인됨' if purchase.is_approved else '대기중',
                purchase.created_at.strftime('%Y-%m-%d %H:%M'),
                '있음' if getattr(purchase, 'attachment_filename', None) else '없음'
            ]
            txt_content += '\t'.join(row) + '\n'
        
        # 다중 품목 구매내역
        multi_purchases = MultiPurchase.query.order_by(MultiPurchase.created_at.desc()).all()
        for multi_purchase in multi_purchases:
            # 각 품목별로 행 생성
            for item in multi_purchase.items:
                row = [
                    f"M{multi_purchase.id}-{item.id}",
                    multi_purchase.team.name,
                    multi_purchase.team.leader_name or '미설정',
                    item.item_name,
                    str(item.quantity),
                    str(item.unit_price * item.quantity),
                    multi_purchase.store,
                    '학과지원사업' if multi_purchase.budget_type == 'department' else '학생지원사업' if multi_purchase.budget_type == 'student' else '미선택',
                    '승인됨' if multi_purchase.is_approved else '대기중',
                    multi_purchase.created_at.strftime('%Y-%m-%d %H:%M'),
                    '있음' if getattr(multi_purchase, 'attachment_filename', None) else '없음'
                ]
                txt_content += '\t'.join(row) + '\n'
    
        # 텍스트 파일로 응답
        response = make_response(txt_content.encode('utf-8'))
        response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=전체_구매내역_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        
        return response
        
    except Exception as e:
        flash('파일 다운로드 중 오류가 발생했습니다.', 'error')
        print(f"❌ 다운로드 오류: {e}")
        return redirect(url_for('admin'))

@app.route('/export_team_excel/<int:team_id>')
def export_team_excel(team_id):
    """특정 조의 구매내역을 엑셀(CSV)로 다운로드"""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    try:
        team = Team.query.get_or_404(team_id)
        
        # Tab 구분 텍스트 파일 생성
        txt_content = ""
        
        # 헤더 작성
        headers = ['ID', '조 번호', '조장', '품목명', '수량', '예상비용', '쇼핑몰', '예산유형', '상태', '요청일시', '견적서첨부']
        txt_content += '\t'.join(headers) + '\n'
        
        # 해당 조의 일반 구매내역
        purchases = Purchase.query.filter_by(team_id=team_id).order_by(Purchase.created_at.desc()).all()
        for purchase in purchases:
            row = [
                str(purchase.id),
                purchase.team.name,
                purchase.team.leader_name or '미설정',
                purchase.item_name,
                str(purchase.quantity),
                str(purchase.estimated_cost),
                purchase.store,
                '학과지원사업' if getattr(purchase, 'budget_type', None) == 'department' else '학생지원사업' if getattr(purchase, 'budget_type', None) == 'student' else '미선택',
                '승인됨' if purchase.is_approved else '대기중',
                purchase.created_at.strftime('%Y-%m-%d %H:%M'),
                '있음' if getattr(purchase, 'attachment_filename', None) else '없음'
            ]
            txt_content += '\t'.join(row) + '\n'
        
        # 해당 조의 다중 품목 구매내역
        multi_purchases = MultiPurchase.query.filter_by(team_id=team_id).order_by(MultiPurchase.created_at.desc()).all()
        for multi_purchase in multi_purchases:
            # 각 품목별로 행 생성
            for item in multi_purchase.items:
                row = [
                    f"M{multi_purchase.id}-{item.id}",
                    multi_purchase.team.name,
                    multi_purchase.team.leader_name or '미설정',
                    item.item_name,
                    str(item.quantity),
                    str(item.unit_price * item.quantity),
                    multi_purchase.store,
                    '학과지원사업' if multi_purchase.budget_type == 'department' else '학생지원사업' if multi_purchase.budget_type == 'student' else '미선택',
                    '승인됨' if multi_purchase.is_approved else '대기중',
                    multi_purchase.created_at.strftime('%Y-%m-%d %H:%M'),
                    '있음' if getattr(multi_purchase, 'attachment_filename', None) else '없음'
                ]
                txt_content += '\t'.join(row) + '\n'
    
        # 텍스트 파일로 응답
        response = make_response(txt_content.encode('utf-8'))
        response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename={team.name}_구매내역_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        
        return response
        
    except Exception as e:
        flash('파일 다운로드 중 오류가 발생했습니다.', 'error')
        print(f"❌ 조별 다운로드 오류: {e}")
        return redirect(url_for('admin'))

@app.route('/view_data')
def view_data():
    """데이터베이스 내용을 웹페이지에서 직접 확인"""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    try:
        # 모든 데이터 수집
        teams = Team.query.all()
        purchases = Purchase.query.all()
        multi_purchases = MultiPurchase.query.all()
        other_requests = OtherRequest.query.all()
        
        # 데이터를 텍스트로 변환
        data_text = "=== 팀 정보 ===\n"
        for team in teams:
            data_text += f"팀: {team.name}, 조장: {team.leader_name or '미설정'}, 학과예산: {team.department_budget}, 학생예산: {team.student_budget}\n"
        
        data_text += "\n=== 구매내역 ===\n"
        for purchase in purchases:
            data_text += f"ID: {purchase.id}, 팀: {purchase.team.name}, 품목: {purchase.item_name}, 수량: {purchase.quantity}, 비용: {purchase.estimated_cost}, 상태: {'승인' if purchase.is_approved else '대기'}\n"
        
        data_text += "\n=== 다중품목 구매내역 ===\n"
        for multi_purchase in multi_purchases:
            data_text += f"ID: {multi_purchase.id}, 팀: {multi_purchase.team.name}, 상태: {'승인' if multi_purchase.is_approved else '대기'}\n"
            for item in multi_purchase.items:
                data_text += f"  - 품목: {item.item_name}, 수량: {item.quantity}, 단가: {item.unit_price}\n"
        
        data_text += "\n=== 기타 요청 ===\n"
        for request in other_requests:
            data_text += f"ID: {request.id}, 팀: {request.team.name}, 내용: {request.content}, 상태: {'승인' if request.is_approved else '대기'}\n"
        
        return f"<pre>{data_text}</pre>"
        
    except Exception as e:
        return f"<pre>오류 발생: {e}</pre>"

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('index'))

def migrate_existing_data():
    """기존 데이터에 새로운 필드 추가 (마이그레이션)"""
    with app.app_context():
        try:
            # 먼저 새로운 컬럼이 있는지 확인
            with db.engine.connect() as conn:
                result = conn.execute(db.text("PRAGMA table_info(team)"))
                columns = [row[1] for row in result]
            
            # original_department_budget 컬럼이 없으면 추가
            if 'original_department_budget' not in columns:
                with db.engine.connect() as conn:
                    conn.execute(db.text("ALTER TABLE team ADD COLUMN original_department_budget INTEGER DEFAULT 0"))
                    conn.commit()
                print("original_department_budget 컬럼을 추가했습니다.")
            
            # original_student_budget 컬럼이 없으면 추가
            if 'original_student_budget' not in columns:
                with db.engine.connect() as conn:
                    conn.execute(db.text("ALTER TABLE team ADD COLUMN original_student_budget INTEGER DEFAULT 0"))
                    conn.commit()
                print("original_student_budget 컬럼을 추가했습니다.")
            
            # Purchase 테이블의 attachment_filename 컬럼 확인 및 추가
            with db.engine.connect() as conn:
                result = conn.execute(db.text("PRAGMA table_info(purchase)"))
                purchase_columns = [row[1] for row in result]
            
            if 'attachment_filename' not in purchase_columns:
                with db.engine.connect() as conn:
                    conn.execute(db.text("ALTER TABLE purchase ADD COLUMN attachment_filename VARCHAR(255)"))
                    conn.commit()
                print("attachment_filename 컬럼을 추가했습니다.")
            
            # 새로운 테이블들 생성 (MultiPurchase, MultiPurchaseItem) - 기존 데이터 보존
            # db.create_all()은 init_db()에서만 호출
            print("테이블 구조 확인 완료.")
            
            # 기존 데이터에 원래 예산 값 설정
            teams = Team.query.all()
            for team in teams:
                if team.original_department_budget == 0:
                    team.original_department_budget = team.department_budget
                if team.original_student_budget == 0:
                    team.original_student_budget = team.student_budget
            
            db.session.commit()
            print("기존 데이터 마이그레이션이 완료되었습니다.")
            
        except Exception as e:
            print(f"마이그레이션 중 오류 발생: {e}")
            # 오류 발생 시에도 데이터를 보존하고 계속 진행
            print("마이그레이션을 건너뛰고 계속 진행합니다.")

def restore_from_json():
    """JSON 백업 파일에서 데이터 복원"""
    try:
        print("🔄 JSON 백업에서 데이터 복원 시도...")
        
        # GitHub에서 팀 데이터 다운로드
        teams_content = download_from_github('teams.json')
        if teams_content:
            teams_data = json.loads(teams_content)
            
            for team_data in teams_data.get('teams', []):
                existing_team = Team.query.get(team_data['id'])
                if existing_team:
                    # 기존 팀 업데이트
                    existing_team.leader_name = team_data['leader_name']
                    existing_team.department_budget = team_data['department_budget']
                    existing_team.student_budget = team_data['student_budget']
                    if hasattr(existing_team, 'original_department_budget'):
                        existing_team.original_department_budget = team_data.get('original_department_budget', team_data['department_budget'])
                    if hasattr(existing_team, 'original_student_budget'):
                        existing_team.original_student_budget = team_data.get('original_student_budget', team_data['student_budget'])
                else:
                    # 새 팀 생성
                    team = Team(
                        id=team_data['id'],
                        name=team_data['name'],
                        leader_name=team_data['leader_name'],
                        department_budget=team_data['department_budget'],
                        student_budget=team_data['student_budget']
                    )
                    if hasattr(team, 'original_department_budget'):
                        team.original_department_budget = team_data.get('original_department_budget', team_data['department_budget'])
                    if hasattr(team, 'original_student_budget'):
                        team.original_student_budget = team_data.get('original_student_budget', team_data['student_budget'])
                    db.session.add(team)
            
            db.session.commit()
            print(f"✅ {len(teams_data.get('teams', []))}개 팀 데이터 복원 완료!")
        
        # GitHub에서 구매내역 다운로드
        purchases_content = download_from_github('purchases.json')
        if purchases_content:
            purchases_data = json.loads(purchases_content)
            
            for purchase_data in purchases_data.get('purchases', []):
                existing_purchase = Purchase.query.get(purchase_data['id'])
                if not existing_purchase:
                    purchase = Purchase(
                        id=purchase_data['id'],
                        team_id=purchase_data['team_id'],
                        item_name=purchase_data['item_name'],
                        quantity=purchase_data['quantity'],
                        estimated_cost=purchase_data['total_amount'],
                        link=purchase_data.get('link', ''),
                        store=purchase_data['store'],
                        is_approved=purchase_data['is_approved'],
                        budget_type=purchase_data.get('budget_type', 'department'),
                        attachment_filename=purchase_data.get('attachment_filename'),
                        request_date=datetime.strptime(purchase_data['request_date'], '%Y-%m-%d %H:%M:%S')
                    )
                    db.session.add(purchase)
            
            db.session.commit()
            print(f"✅ {len(purchases_data.get('purchases', []))}개 구매내역 복원 완료!")
        
        return True
        
    except Exception as e:
        print(f"❌ JSON 복원 오류: {e}")
        return False

def init_db():
    """데이터베이스 초기화 (기존 데이터 절대 보존)"""
    with app.app_context():
        try:
            # 1. 기존 데이터베이스 파일이 있는지 확인
            if os.path.exists('budget_management.db'):
                print("✅ 기존 데이터베이스 파일 발견! 데이터를 보존합니다.")
                # 기존 데이터 확인
                existing_teams = Team.query.count()
                print(f"기존 팀 개수: {existing_teams}")
                for team in Team.query.all():
                    print(f"  - {team.name}: 조장={team.leader_name or '미설정'}")
                
                # 기존 데이터가 있어도 JSON 백업 실행
                print("🔄 기존 데이터 JSON 백업 실행...")
                backup_to_json()
                return
            
            print("📝 새로운 데이터베이스 파일 생성...")
            
            # 2. 테이블 생성
            db.create_all()
            
            # 3. JSON 백업에서 데이터 복원 시도
            restore_from_json()
            print("테이블 생성 완료")
            
            # 3. 초기 팀 데이터 생성 (새 데이터베이스일 때만)
            teams_data = [
                {'name': '월요일 1조', 'department_budget': 600000, 'student_budget': 500000, 'original_department_budget': 600000, 'original_student_budget': 500000},
                {'name': '월요일 2조', 'department_budget': 700000, 'student_budget': 500000, 'original_department_budget': 700000, 'original_student_budget': 500000},
                {'name': '월요일 3조', 'department_budget': 600000, 'student_budget': 500000, 'original_department_budget': 600000, 'original_student_budget': 500000},
                {'name': '월요일 4조', 'department_budget': 700000, 'student_budget': 500000, 'original_department_budget': 700000, 'original_student_budget': 500000},
                {'name': '화요일 1조', 'department_budget': 600000, 'student_budget': 500000, 'original_department_budget': 600000, 'original_student_budget': 500000},
                {'name': '화요일 2조', 'department_budget': 700000, 'student_budget': 500000, 'original_department_budget': 700000, 'original_student_budget': 500000},
                {'name': '화요일 3조', 'department_budget': 600000, 'student_budget': 500000, 'original_department_budget': 600000, 'original_student_budget': 500000},
                {'name': '화요일 4조', 'department_budget': 700000, 'student_budget': 500000, 'original_department_budget': 700000, 'original_student_budget': 500000},
                {'name': '화요일 5조', 'department_budget': 600000, 'student_budget': 500000, 'original_department_budget': 600000, 'original_student_budget': 500000},
                {'name': '화요일 6조', 'department_budget': 700000, 'student_budget': 500000, 'original_department_budget': 700000, 'original_student_budget': 500000},
                {'name': '화요일 7조', 'department_budget': 600000, 'student_budget': 500000, 'original_department_budget': 600000, 'original_student_budget': 500000},
            ]
            
            for team_data in teams_data:
                team = Team(**team_data)
                db.session.add(team)
            db.session.commit()
            print("초기 팀 데이터가 생성되었습니다.")
            
            print("🎉 데이터베이스 초기화 완료!")
            
            # JSON 백업 실행
            print("🔄 초기화 후 JSON 백업 실행...")
            backup_to_json()
            
        except Exception as e:
            print(f"❌ 데이터베이스 초기화 중 오류: {e}")
            # 오류 발생 시에도 기존 데이터 보존
            print("오류 발생했지만 기존 데이터는 보존됩니다.")

# view_data 라우트는 이미 정의되어 있음 (중복 제거)

@app.route('/reset_database', methods=['POST'])
def reset_database():
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    try:
        # 모든 데이터 삭제
        MultiPurchaseItem.query.delete()
        MultiPurchase.query.delete()
        Purchase.query.delete()
        OtherRequest.query.delete()
        Team.query.delete()
        
        # 기본 팀들 재생성
        default_teams = [
            Team(name='월요일 1조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='월요일 2조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='월요일 3조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='월요일 4조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='화요일 1조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='화요일 2조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='화요일 3조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='화요일 4조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='화요일 5조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='화요일 6조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='화요일 7조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0)
        ]
        
        for team in default_teams:
            db.session.add(team)
        
        db.session.commit()
        flash('데이터베이스가 성공적으로 초기화되었습니다.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('데이터베이스 초기화 중 오류가 발생했습니다.', 'error')
        print(f"❌ 데이터베이스 초기화 오류: {e}")
    
    return redirect(url_for('admin'))

if __name__ == '__main__':
    # 데이터베이스 초기화 (기존 데이터 보존)
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
    print("   - 데이터베이스 보기 (다운로드 기능 제거됨)")
    print("=" * 60)
    
    # Render 배포를 위한 포트 설정
    import os
    port = int(os.environ.get('PORT', PORT))
    # 운영 환경에서는 디버그 모드 비활성화
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
