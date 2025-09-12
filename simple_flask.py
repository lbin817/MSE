#!/usr/bin/env python3
"""
간단한 Flask 서버 (Flask-WTF 없이)
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
import ipaddress
from werkzeug.utils import secure_filename
import uuid
import io
import csv
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
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 제한

# 업로드 폴더 생성
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

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
            
            # 새로운 테이블들 생성 (MultiPurchase, MultiPurchaseItem)
            db.create_all()
            print("새로운 테이블들이 생성되었습니다.")
            
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
            # 오류 발생 시 데이터베이스 재생성
            db.drop_all()
            db.create_all()
            print("데이터베이스를 재생성했습니다.")

def init_db():
    """데이터베이스 초기화 및 초기 데이터 설정 (데이터 보존)"""
    with app.app_context():
        # 테이블 생성 (기존 데이터 보존)
        db.create_all()
        
        # 기존 데이터 마이그레이션
        migrate_existing_data()
        
        # 초기 팀 데이터 (기존 팀이 없을 때만 생성)
        teams_data = [
            {'name': '1조', 'department_budget': 600000, 'student_budget': 500000, 'original_department_budget': 600000, 'original_student_budget': 500000},
            {'name': '2조', 'department_budget': 700000, 'student_budget': 500000, 'original_department_budget': 700000, 'original_student_budget': 500000},
            {'name': '3조', 'department_budget': 600000, 'student_budget': 500000, 'original_department_budget': 600000, 'original_student_budget': 500000},
            {'name': '4조', 'department_budget': 700000, 'student_budget': 500000, 'original_department_budget': 700000, 'original_student_budget': 500000},
            {'name': '5조', 'department_budget': 600000, 'student_budget': 500000, 'original_department_budget': 600000, 'original_student_budget': 500000},
            {'name': '6조', 'department_budget': 700000, 'student_budget': 500000, 'original_department_budget': 700000, 'original_student_budget': 500000},
            {'name': '7조', 'department_budget': 600000, 'student_budget': 500000, 'original_department_budget': 600000, 'original_student_budget': 500000},
            {'name': '8조', 'department_budget': 700000, 'student_budget': 500000, 'original_department_budget': 700000, 'original_student_budget': 500000},
            {'name': '9조', 'department_budget': 600000, 'student_budget': 500000, 'original_department_budget': 600000, 'original_student_budget': 500000},
            {'name': '10조', 'department_budget': 600000, 'student_budget': 500000, 'original_department_budget': 600000, 'original_student_budget': 500000},
        ]
        
        # 기존 팀이 없을 때만 새로 생성 (데이터 보존)
        existing_teams = Team.query.count()
        if existing_teams == 0:
            for team_data in teams_data:
                team = Team(**team_data)
                db.session.add(team)
            db.session.commit()
            print("초기 팀 데이터가 생성되었습니다.")
        else:
            print(f"기존 {existing_teams}개 팀 데이터를 보존했습니다.")
        
        print("데이터베이스 초기화가 완료되었습니다.")

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
            Team(name='1조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='2조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='3조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='4조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='5조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='6조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='7조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='8조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='9조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0),
            Team(name='10조', leader_name='', department_budget=0, student_budget=0, original_department_budget=0, original_student_budget=0)
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
    # Render 배포를 위한 포트 설정
    import os
    port = int(os.environ.get('PORT', PORT))
    # 운영 환경에서는 디버그 모드 비활성화
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
