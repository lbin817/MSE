from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, SelectField, PasswordField, SubmitField
from wtforms.validators import DataRequired, NumberRange
from werkzeug.security import check_password_hash, generate_password_hash
import os
from datetime import datetime
import ipaddress
import csv
import io
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
    department_budget = db.Column(db.Integer, nullable=False)  # 학과지원사업
    student_budget = db.Column(db.Integer, nullable=False)     # 학생지원사업
    
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
    budget_type = db.Column(db.String(20), nullable=True)  # 'department' or 'student'
    attachment_filename = db.Column(db.String(255), nullable=True)
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
    attachment_filename = db.Column(db.String(255), nullable=True)
    is_approved = db.Column(db.Boolean, default=False)
    budget_type = db.Column(db.String(50), nullable=True)
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
    teams = Team.query.all()
    
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
    
    return render_template('upload.html', teams=teams)

@app.route('/check_balance', methods=['GET', 'POST'])
def check_balance():
    teams = Team.query.all()
    balance_info = None
    
    if request.method == 'POST':
        team_name = request.form.get('team_name')
        leader_name = request.form.get('leader_name')
        
        team = Team.query.filter_by(name=team_name).first()
        if team and team.leader_name == leader_name:
            # 승인된 구매내역의 총액 계산
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
    
    return render_template('check_balance.html', teams=teams, balance_info=balance_info)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    teams = Team.query.all()
    
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
    
    # 모든 조의 잔여금액 정보
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
            'total_budget': team.department_budget + team.student_budget,
            'total_spent': total_spent,
            'remaining': (team.department_budget + team.student_budget) - total_spent
        })
    
    # 승인 대기 중인 구매내역
    pending_purchases = Purchase.query.filter_by(is_approved=False).all()
    pending_multi_purchases = MultiPurchase.query.filter_by(is_approved=False).all()
    
    # 기타 구매 요청
    other_requests = OtherRequest.query.all()
    
    # 모든 구매내역 (일반)
    all_purchases = Purchase.query.order_by(Purchase.created_at.desc()).all()
    
    # 다중 품목 구매내역
    all_multi_purchases = MultiPurchase.query.order_by(MultiPurchase.created_at.desc()).all()
    
    # 전체 예산 통계 계산
    total_budget = sum(team['total_budget'] for team in all_teams_info) if all_teams_info else 0
    total_spent = sum(team['total_spent'] for team in all_teams_info) if all_teams_info else 0
    total_remaining = sum(team['remaining'] for team in all_teams_info) if all_teams_info else 0
    
    return render_template('admin.html', 
                         teams=teams,
                         all_teams_info=all_teams_info,
                         pending_purchases=pending_purchases,
                         pending_multi_purchases=pending_multi_purchases,
                         other_requests=other_requests,
                         all_purchases=all_purchases,
                         all_multi_purchases=all_multi_purchases,
                         total_budget=total_budget,
                         total_spent=total_spent,
                         total_remaining=total_remaining)

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
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    try:
        file_path = os.path.join('uploads', filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            flash('파일을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin'))
    except Exception as e:
        flash('파일 다운로드 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin'))


@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('index'))

@app.route('/export_excel')
def export_excel():
    """전체 구매내역을 엑셀(CSV)로 다운로드"""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    # CSV 데이터 생성 (UTF-8 BOM 포함)
    output = io.BytesIO()
    output.write('\ufeff'.encode('utf-8'))  # UTF-8 BOM 추가
    writer = csv.writer(io.TextIOWrapper(output, encoding='utf-8'))
    
    # 헤더 작성
    writer.writerow([
        'ID', '조 번호', '조장', '품목명', '수량', '예상비용', '쇼핑몰', 
        '예산유형', '상태', '요청일시'
    ])
    
    # 일반 구매내역
    purchases = Purchase.query.order_by(Purchase.created_at.desc()).all()
    for purchase in purchases:
        writer.writerow([
            purchase.id,
            purchase.team.name,
            purchase.team.leader_name or '미설정',
            purchase.item_name,
            purchase.quantity,
            purchase.estimated_cost,
            purchase.store,
            '학과지원사업' if getattr(purchase, 'budget_type', None) == 'department' else '학생지원사업' if getattr(purchase, 'budget_type', None) == 'student' else '미선택',
            '승인됨' if purchase.is_approved else '대기중',
            purchase.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    
    # 다중 품목 구매내역
    multi_purchases = MultiPurchase.query.order_by(MultiPurchase.created_at.desc()).all()
    for multi_purchase in multi_purchases:
        # 각 품목별로 행 생성
        for item in multi_purchase.items:
            writer.writerow([
                f"M{multi_purchase.id}-{item.id}",
                multi_purchase.team.name,
                multi_purchase.team.leader_name or '미설정',
                item.item_name,
                item.quantity,
                item.unit_price * item.quantity,
                multi_purchase.store,
                '학과지원사업' if multi_purchase.budget_type == 'department' else '학생지원사업' if multi_purchase.budget_type == 'student' else '미선택',
                '승인됨' if multi_purchase.is_approved else '대기중',
                multi_purchase.created_at.strftime('%Y-%m-%d %H:%M')
            ])
    
    # CSV 파일로 응답
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    response.headers['Content-Disposition'] = f'attachment; filename=purchase_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return response

@app.route('/export_team_excel/<int:team_id>')
def export_team_excel(team_id):
    """특정 조의 구매내역을 엑셀(CSV)로 다운로드"""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    team = Team.query.get_or_404(team_id)
    
    # CSV 데이터 생성 (UTF-8 BOM 포함)
    output = io.BytesIO()
    output.write('\ufeff'.encode('utf-8'))  # UTF-8 BOM 추가
    writer = csv.writer(io.TextIOWrapper(output, encoding='utf-8'))
    
    # 헤더 작성
    writer.writerow([
        'ID', '조 번호', '조장', '품목명', '수량', '예상비용', '쇼핑몰', 
        '예산유형', '상태', '요청일시'
    ])
    
    # 해당 조의 일반 구매내역
    purchases = Purchase.query.filter_by(team_id=team_id).order_by(Purchase.created_at.desc()).all()
    for purchase in purchases:
        writer.writerow([
            purchase.id,
            purchase.team.name,
            purchase.team.leader_name or '미설정',
            purchase.item_name,
            purchase.quantity,
            purchase.estimated_cost,
            purchase.store,
            '학과지원사업' if getattr(purchase, 'budget_type', None) == 'department' else '학생지원사업' if getattr(purchase, 'budget_type', None) == 'student' else '미선택',
            '승인됨' if purchase.is_approved else '대기중',
            purchase.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    
    # 해당 조의 다중 품목 구매내역
    multi_purchases = MultiPurchase.query.filter_by(team_id=team_id).order_by(MultiPurchase.created_at.desc()).all()
    for multi_purchase in multi_purchases:
        # 각 품목별로 행 생성
        for item in multi_purchase.items:
            writer.writerow([
                f"M{multi_purchase.id}-{item.id}",
                multi_purchase.team.name,
                multi_purchase.team.leader_name or '미설정',
                item.item_name,
                item.quantity,
                item.unit_price * item.quantity,
                multi_purchase.store,
                '학과지원사업' if multi_purchase.budget_type == 'department' else '학생지원사업' if multi_purchase.budget_type == 'student' else '미선택',
                '승인됨' if multi_purchase.is_approved else '대기중',
                multi_purchase.created_at.strftime('%Y-%m-%d %H:%M')
            ])
    
    # CSV 파일로 응답
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    response.headers['Content-Disposition'] = f'attachment; filename={team.name}_purchase_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return response

def init_db():
    """데이터베이스 테이블 생성 및 초기 데이터 설정 (기존 데이터 보존)"""
    with app.app_context():
        # 테이블만 생성 (기존 데이터는 보존)
        db.create_all()
        
        # 초기 조 데이터 설정 (없는 조만 추가)
        teams_data = [
            # 월요일 조들
            {'name': '월요일 1조', 'department_budget': 600000, 'student_budget': 500000},
            {'name': '월요일 2조', 'department_budget': 700000, 'student_budget': 500000},
            {'name': '월요일 3조', 'department_budget': 600000, 'student_budget': 500000},
            {'name': '월요일 4조', 'department_budget': 700000, 'student_budget': 500000},
            # 화요일 조들
            {'name': '화요일 1조', 'department_budget': 600000, 'student_budget': 500000},
            {'name': '화요일 2조', 'department_budget': 700000, 'student_budget': 500000},
            {'name': '화요일 3조', 'department_budget': 600000, 'student_budget': 500000},
            {'name': '화요일 4조', 'department_budget': 700000, 'student_budget': 500000},
            {'name': '화요일 5조', 'department_budget': 600000, 'student_budget': 500000},
            {'name': '화요일 6조', 'department_budget': 700000, 'student_budget': 500000},
            {'name': '화요일 7조', 'department_budget': 600000, 'student_budget': 500000},
        ]
        
        # 기존에 없는 조만 추가 (기존 데이터 보존)
        for team_data in teams_data:
            existing_team = Team.query.filter_by(name=team_data['name']).first()
            if not existing_team:
                team = Team(**team_data)
                db.session.add(team)
                print(f"새로운 조 추가: {team_data['name']}")
        
        db.session.commit()
        print("데이터베이스 테이블이 확인되었습니다. (기존 데이터 보존)")

if __name__ == '__main__':
    init_db()
    app.run(debug=DEBUG, host=HOST, port=PORT, ssl_context='adhoc')
