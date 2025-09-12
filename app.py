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
import codecs
from config import ALLOWED_IPS, ADMIN_USERNAME, ADMIN_PASSWORD, HOST, PORT, DEBUG

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# 환경별 데이터베이스 설정
import os

# Render 배포 환경에서는 PostgreSQL 사용, 로컬에서는 SQLite 사용
if os.environ.get('RENDER'):
    # Render 배포 환경 (PostgreSQL)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    print("🌐 PostgreSQL 데이터베이스 사용 (Render 배포 환경)")
else:
    # 로컬 개발 환경 (SQLite)
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'budget_management.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    print(f"💻 SQLite 데이터베이스 사용 (로컬): {db_path}")

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
    original_department_budget = db.Column(db.Integer, nullable=False, default=0)  # 원본 학과지원사업 예산
    original_student_budget = db.Column(db.Integer, nullable=False, default=0)     # 원본 학생지원사업 예산
    
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
    
    # 데이터 수집
    data = []
    
    # 일반 구매내역
    purchases = Purchase.query.order_by(Purchase.created_at.desc()).all()
    for purchase in purchases:
        data.append({
            'ID': purchase.id,
            '조 번호': purchase.team.name,
            '조장': purchase.team.leader_name or '미설정',
            '품목명': purchase.item_name,
            '수량': purchase.quantity,
            '예상비용': purchase.estimated_cost,
            '쇼핑몰': purchase.store,
            '예산유형': '학과지원사업' if getattr(purchase, 'budget_type', None) == 'department' else '학생지원사업' if getattr(purchase, 'budget_type', None) == 'student' else '미선택',
            '상태': '승인됨' if purchase.is_approved else '대기중',
            '요청일시': purchase.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    # 다중 품목 구매내역
    multi_purchases = MultiPurchase.query.order_by(MultiPurchase.created_at.desc()).all()
    for multi_purchase in multi_purchases:
        for item in multi_purchase.items:
            data.append({
                'ID': f"M{multi_purchase.id}-{item.id}",
                '조 번호': multi_purchase.team.name,
                '조장': multi_purchase.team.leader_name or '미설정',
                '품목명': item.item_name,
                '수량': item.quantity,
                '예상비용': item.unit_price * item.quantity,
                '쇼핑몰': multi_purchase.store,
                '예산유형': '학과지원사업' if multi_purchase.budget_type == 'department' else '학생지원사업' if multi_purchase.budget_type == 'student' else '미선택',
                '상태': '승인됨' if multi_purchase.is_approved else '대기중',
                '요청일시': multi_purchase.created_at.strftime('%Y-%m-%d %H:%M')
            })
    
    # CSV 생성 (UTF-8 BOM 포함) - 가장 간단한 방법
    csv_content = ""
    
    # UTF-8 BOM 추가
    csv_content += '\ufeff'
    
    # 헤더 작성
    if data:
        headers = list(data[0].keys())
        csv_content += ','.join(f'"{h}"' for h in headers) + '\n'
        
        # 데이터 작성
        for row in data:
            csv_content += ','.join(f'"{str(row[header])}"' for header in headers) + '\n'
    
    # 응답 생성
    response = make_response(csv_content.encode('utf-8-sig'))
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    response.headers['Content-Disposition'] = f'attachment; filename=purchase_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return response

@app.route('/export_team_excel/<int:team_id>')
def export_team_excel(team_id):
    """특정 조의 구매내역을 엑셀(CSV)로 다운로드"""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    team = Team.query.get_or_404(team_id)
    
    # 데이터 수집
    data = []
    
    # 해당 조의 일반 구매내역
    purchases = Purchase.query.filter_by(team_id=team_id).order_by(Purchase.created_at.desc()).all()
    for purchase in purchases:
        data.append({
            'ID': purchase.id,
            '조 번호': purchase.team.name,
            '조장': purchase.team.leader_name or '미설정',
            '품목명': purchase.item_name,
            '수량': purchase.quantity,
            '예상비용': purchase.estimated_cost,
            '쇼핑몰': purchase.store,
            '예산유형': '학과지원사업' if getattr(purchase, 'budget_type', None) == 'department' else '학생지원사업' if getattr(purchase, 'budget_type', None) == 'student' else '미선택',
            '상태': '승인됨' if purchase.is_approved else '대기중',
            '요청일시': purchase.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    # 해당 조의 다중 품목 구매내역
    multi_purchases = MultiPurchase.query.filter_by(team_id=team_id).order_by(MultiPurchase.created_at.desc()).all()
    for multi_purchase in multi_purchases:
        for item in multi_purchase.items:
            data.append({
                'ID': f"M{multi_purchase.id}-{item.id}",
                '조 번호': multi_purchase.team.name,
                '조장': multi_purchase.team.leader_name or '미설정',
                '품목명': item.item_name,
                '수량': item.quantity,
                '예상비용': item.unit_price * item.quantity,
                '쇼핑몰': multi_purchase.store,
                '예산유형': '학과지원사업' if multi_purchase.budget_type == 'department' else '학생지원사업' if multi_purchase.budget_type == 'student' else '미선택',
                '상태': '승인됨' if multi_purchase.is_approved else '대기중',
                '요청일시': multi_purchase.created_at.strftime('%Y-%m-%d %H:%M')
            })
    
    # CSV 생성 (UTF-8 BOM 포함) - 가장 간단한 방법
    csv_content = ""
    
    # UTF-8 BOM 추가
    csv_content += '\ufeff'
    
    # 헤더 작성
    if data:
        headers = list(data[0].keys())
        csv_content += ','.join(f'"{h}"' for h in headers) + '\n'
        
        # 데이터 작성
        for row in data:
            csv_content += ','.join(f'"{str(row[header])}"' for header in headers) + '\n'
    
    # 응답 생성
    response = make_response(csv_content.encode('utf-8-sig'))
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    response.headers['Content-Disposition'] = f'attachment; filename={team.name}_purchase_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return response

@app.route('/reset_database', methods=['POST'])
def reset_database():
    """데이터베이스 초기화 (관리자만 가능)"""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    try:
        # 모든 데이터 삭제
        db.session.query(MultiPurchaseItem).delete()
        db.session.query(MultiPurchase).delete()
        db.session.query(Purchase).delete()
        db.session.query(OtherRequest).delete()
        db.session.query(Team).delete()
        
        # 기본 조들 생성
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
        
        for team_data in teams_data:
            team = Team(**team_data)
            db.session.add(team)
        
        db.session.commit()
        flash('데이터베이스가 성공적으로 초기화되었습니다.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'데이터베이스 초기화 중 오류가 발생했습니다: {e}', 'error')
    
    return redirect(url_for('admin'))

def init_db():
    """데이터베이스 테이블 생성 및 초기 데이터 설정 (기존 데이터 보존)"""
    with app.app_context():
        try:
            # 환경별 데이터베이스 정보 출력
            if os.environ.get('RENDER'):
                print("🗄️  PostgreSQL 데이터베이스 (Render 클라우드)")
                print("☁️  데이터는 클라우드에 영구 저장됩니다")
            else:
                # 로컬 SQLite 파일 존재 여부 확인
                db_file_exists = os.path.exists(db_path)
                print(f"🗄️  SQLite 데이터베이스 파일: {db_path}")
                print(f"📁 파일 존재 여부: {'✅ 존재함' if db_file_exists else '❌ 없음 (새로 생성)'}")
            
            # 테이블만 생성 (기존 데이터는 보존)
            db.create_all()
            
            # 데이터베이스 마이그레이션 - 새로운 필드들 추가
            try:
                # 기존 조들에 original_department_budget, original_student_budget 필드 추가
                teams = Team.query.all()
                migration_count = 0
                for team in teams:
                    try:
                        # original_department_budget 필드가 없거나 0인 경우
                        if not hasattr(team, 'original_department_budget') or getattr(team, 'original_department_budget', 0) == 0:
                            team.original_department_budget = team.department_budget or 0
                            migration_count += 1
                        
                        # original_student_budget 필드가 없거나 0인 경우
                        if not hasattr(team, 'original_student_budget') or getattr(team, 'original_student_budget', 0) == 0:
                            team.original_student_budget = team.student_budget or 0
                            migration_count += 1
                    except Exception as team_error:
                        print(f"⚠️  조 {team.name} 마이그레이션 중 오류: {team_error}")
                        continue
                
                if migration_count > 0:
                    db.session.commit()
                    print(f"✅ {migration_count}개 필드 마이그레이션이 완료되었습니다.")
                else:
                    print("✅ 마이그레이션이 필요하지 않습니다.")
            except Exception as e:
                print(f"⚠️  마이그레이션 중 오류 발생 (정상): {e}")
                db.session.rollback()
            
            # 기존 데이터 확인
            existing_teams_count = Team.query.count()
            existing_purchases_count = Purchase.query.count()
            existing_requests_count = OtherRequest.query.count()
            
            print(f"📊 기존 데이터 확인:")
            print(f"   - 조: {existing_teams_count}개")
            print(f"   - 구매내역: {existing_purchases_count}개")
            print(f"   - 기타 요청: {existing_requests_count}개")
            
            # 자동 초기화 완전 비활성화 - 사용자가 초기화 버튼을 눌러야만 초기화됨
            print("🔒 자동 초기화가 비활성화되었습니다.")
            print("💾 조장 이름, 구매내역 등 모든 데이터가 영구 보존됩니다!")
            print(f"📊 현재 데이터 상태:")
            print(f"   - 조: {existing_teams_count}개")
            print(f"   - 구매내역: {existing_purchases_count}개")
            print(f"   - 기타 요청: {existing_requests_count}개")
            print("⚠️  데이터 초기화는 관리자 모드의 '초기화' 버튼을 통해서만 가능합니다!")
            
            # 조가 하나도 없을 때만 기본 조들 생성
            if existing_teams_count == 0:
                print("🆕 조가 없으므로 기본 조들을 생성합니다.")
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
                
                for team_data in teams_data:
                    team = Team(**team_data)
                    db.session.add(team)
                    print(f"✅ 기본 조 생성: {team_data['name']}")
                
                db.session.commit()
                print("🆕 기본 조들이 생성되었습니다.")
            else:
                print("✅ 기존 조들이 보존되었습니다.")
                
            print("🔒 데이터베이스 테이블이 안전하게 확인되었습니다. (기존 데이터 보존)")
            
        except Exception as e:
            print(f"❌ 데이터베이스 초기화 중 오류 발생: {e}")
            print("🔄 기존 데이터를 보존하기 위해 계속 진행합니다.")
            db.session.rollback()

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
    print("=" * 60)
    print("⚠️  주의: 데이터베이스는 자동으로 보존됩니다!")
    print("=" * 60)
    
    # Render 배포를 위한 포트 설정
    import os
    port = int(os.environ.get('PORT', PORT))
    # 운영 환경에서는 디버그 모드 비활성화
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
