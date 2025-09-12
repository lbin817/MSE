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

@app.before_request
def check_ip():
    """모든 요청에 대해 IP 제한 확인"""
    if request.remote_addr and not is_allowed_ip(request.remote_addr):
        return "접근이 제한된 IP 주소입니다.", 403

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

# 폼 클래스
class PurchaseForm(FlaskForm):
    team_name = SelectField('조 번호', choices=[], validators=[DataRequired()])
    leader_name = StringField('조장 이름', validators=[DataRequired()])
    item_name = StringField('품목명', validators=[DataRequired()])
    quantity = IntegerField('수량', validators=[DataRequired(), NumberRange(min=1)])
    estimated_cost = IntegerField('활용예정 금액 (원)', validators=[DataRequired(), NumberRange(min=1)])
    link = StringField('링크', validators=[DataRequired()])
    store = SelectField('쇼핑몰', choices=[
        ('시그마알드리치', '시그마알드리치'),
        ('4science', '4science'),
        ('디바이스마트', '디바이스마트'),
        ('기타', '기타'),
        ('아마존', '아마존'),
        ('쿠팡', '쿠팡'),
        ('G마켓', 'G마켓')
    ], validators=[DataRequired()])
    submit = SubmitField('업로드')

class OtherRequestForm(FlaskForm):
    team_name = SelectField('조 번호', choices=[], validators=[DataRequired()])
    leader_name = StringField('조장 이름', validators=[DataRequired()])
    content = TextAreaField('구매 요청 내용', validators=[DataRequired()])
    submit = SubmitField('요청하기')

class TeamCheckForm(FlaskForm):
    team_name = SelectField('조 번호', choices=[], validators=[DataRequired()])
    leader_name = StringField('조장 이름', validators=[DataRequired()])
    submit = SubmitField('확인')

class AdminLoginForm(FlaskForm):
    username = StringField('아이디', validators=[DataRequired()])
    password = PasswordField('비밀번호', validators=[DataRequired()])
    submit = SubmitField('로그인')

class LeaderUpdateForm(FlaskForm):
    team_name = SelectField('조 번호', choices=[], validators=[DataRequired()])
    leader_name = StringField('조장 이름', validators=[DataRequired()])
    submit = SubmitField('업데이트')

# 라우트
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    purchase_form = PurchaseForm()
    other_form = OtherRequestForm()
    
    # 조 목록 업데이트
    teams = Team.query.all()
    team_choices = [(team.name, team.name) for team in teams]
    purchase_form.team_name.choices = team_choices
    other_form.team_name.choices = team_choices
    
    if purchase_form.validate_on_submit():
        team = Team.query.filter_by(name=purchase_form.team_name.data).first()
        if team and team.leader_name == purchase_form.leader_name.data:
            purchase = Purchase(
                team_id=team.id,
                item_name=purchase_form.item_name.data,
                quantity=purchase_form.quantity.data,
                estimated_cost=purchase_form.estimated_cost.data,
                link=purchase_form.link.data,
                store=purchase_form.store.data
            )
            db.session.add(purchase)
            db.session.commit()
            flash('구매내역이 성공적으로 업로드되었습니다.', 'success')
            return redirect(url_for('upload'))
        else:
            flash('조장 이름이 일치하지 않습니다.', 'error')
    
    if other_form.validate_on_submit():
        team = Team.query.filter_by(name=other_form.team_name.data).first()
        if team and team.leader_name == other_form.leader_name.data:
            other_request = OtherRequest(
                team_id=team.id,
                content=other_form.content.data
            )
            db.session.add(other_request)
            db.session.commit()
            flash('기타 구매 요청이 성공적으로 제출되었습니다.', 'success')
            return redirect(url_for('upload'))
        else:
            flash('조장 이름이 일치하지 않습니다.', 'error')
    
    return render_template('upload.html', purchase_form=purchase_form, other_form=other_form)

@app.route('/check_balance', methods=['GET', 'POST'])
def check_balance():
    form = TeamCheckForm()
    teams = Team.query.all()
    form.team_name.choices = [(team.name, team.name) for team in teams]
    
    balance_info = None
    
    if form.validate_on_submit():
        team = Team.query.filter_by(name=form.team_name.data).first()
        if team and team.leader_name == form.leader_name.data:
            # 승인된 구매내역의 총액 계산
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
    
    return render_template('check_balance.html', form=form, balance_info=balance_info)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    login_form = AdminLoginForm()
    leader_form = LeaderUpdateForm()
    
    teams = Team.query.all()
    leader_form.team_name.choices = [(team.name, team.name) for team in teams]
    
    if 'admin_logged_in' not in session:
        if login_form.validate_on_submit():
            if login_form.username.data == ADMIN_USERNAME and login_form.password.data == ADMIN_PASSWORD:
                session['admin_logged_in'] = True
                flash('관리자로 로그인되었습니다.', 'success')
                return redirect(url_for('admin'))
            else:
                flash('아이디 또는 비밀번호가 올바르지 않습니다.', 'error')
        
        return render_template('admin_login.html', form=login_form)
    
    # 관리자 로그인 후
    if leader_form.validate_on_submit():
        team = Team.query.filter_by(name=leader_form.team_name.data).first()
        if team:
            team.leader_name = leader_form.leader_name.data
            db.session.commit()
            flash('조장 정보가 업데이트되었습니다.', 'success')
            return redirect(url_for('admin'))
    
    # 모든 조의 잔여금액 정보
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
    
    # 승인 대기 중인 구매내역
    pending_purchases = Purchase.query.filter_by(is_approved=False).all()
    
    # 기타 구매 요청
    other_requests = OtherRequest.query.all()
    
    # 모든 구매내역 (일반)
    all_purchases = Purchase.query.order_by(Purchase.created_at.desc()).all()
    
    # 다중 품목 구매내역 (현재는 없음)
    all_multi_purchases = []
    
    # 전체 예산 통계 계산
    total_budget = sum(team['total_budget'] for team in all_teams_info)
    total_spent = sum(team['total_spent'] for team in all_teams_info)
    total_remaining = sum(team['remaining'] for team in all_teams_info)
    
    return render_template('admin.html', 
                         leader_form=leader_form,
                         teams=teams,
                         all_teams_info=all_teams_info,
                         pending_purchases=pending_purchases,
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
    purchase.is_approved = True
    purchase.budget_type = request.form.get('budget_type', 'department')
    db.session.commit()
    flash('구매내역이 승인되었습니다.', 'success')
    return redirect(url_for('admin'))

@app.route('/cancel_approval/<int:purchase_id>')
def cancel_approval(purchase_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    purchase = Purchase.query.get_or_404(purchase_id)
    purchase.is_approved = False
    purchase.budget_type = None
    db.session.commit()
    flash('승인이 취소되었습니다.', 'info')
    return redirect(url_for('admin'))

@app.route('/delete_purchase/<int:purchase_id>')
def delete_purchase(purchase_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    purchase = Purchase.query.get_or_404(purchase_id)
    db.session.delete(purchase)
    db.session.commit()
    flash('구매내역이 삭제되었습니다.', 'info')
    return redirect(url_for('admin'))

@app.route('/download_file/<filename>')
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

# 다중 품목 관련 더미 라우트들 (현재는 사용하지 않음)
@app.route('/approve_multi_purchase/<int:multi_purchase_id>', methods=['POST'])
def approve_multi_purchase(multi_purchase_id):
    flash('다중 품목 기능은 현재 사용할 수 없습니다.', 'info')
    return redirect(url_for('admin'))

@app.route('/cancel_multi_approval/<int:multi_purchase_id>')
def cancel_multi_approval(multi_purchase_id):
    flash('다중 품목 기능은 현재 사용할 수 없습니다.', 'info')
    return redirect(url_for('admin'))

@app.route('/delete_multi_purchase/<int:multi_purchase_id>')
def delete_multi_purchase(multi_purchase_id):
    flash('다중 품목 기능은 현재 사용할 수 없습니다.', 'info')
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
