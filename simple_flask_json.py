#!/usr/bin/env python3
"""
JSON 파일 기반 Flask 서버 (데이터 영구 보존)
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, make_response
import os
import json
from datetime import datetime
import ipaddress
from werkzeug.utils import secure_filename
import uuid
import io
import csv
from config import ALLOWED_IPS, ADMIN_USERNAME, ADMIN_PASSWORD

# 기본 설정
HOST = '0.0.0.0'
PORT = 5000
DEBUG = False

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# JSON 파일 경로 설정
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
TEAMS_FILE = os.path.join(DATA_DIR, 'teams.json')
PURCHASES_FILE = os.path.join(DATA_DIR, 'purchases.json')
MULTI_PURCHASES_FILE = os.path.join(DATA_DIR, 'multi_purchases.json')
OTHER_REQUESTS_FILE = os.path.join(DATA_DIR, 'other_requests.json')

print(f"📁 JSON 데이터 디렉토리: {DATA_DIR}")

# 파일 업로드 설정
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB 제한 (견적서용)

# 업로드 폴더 생성
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

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

# JSON 파일 읽기/쓰기 함수들
def load_json(file_path):
    """JSON 파일 로드"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"❌ JSON 파일 로드 오류 ({file_path}): {e}")
        return {}

def save_json(file_path, data):
    """JSON 파일 저장"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ JSON 파일 저장 오류 ({file_path}): {e}")
        return False

def get_next_id(data_list, id_key='id'):
    """다음 ID 생성"""
    if not data_list:
        return 1
    return max(item.get(id_key, 0) for item in data_list) + 1

def init_data():
    """데이터 초기화 (기존 데이터 보존)"""
    print("🔄 데이터 초기화 시작...")
    
    # data 디렉토리 생성
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # 팀 데이터 확인 및 초기화
    teams_data = load_json(TEAMS_FILE)
    if not teams_data.get('teams'):
        print("📝 초기 팀 데이터 생성...")
        teams_data = {
            "teams": [
                {"id": 1, "name": "월요일 1조", "leader_name": "", "department_budget": 600000, "student_budget": 500000, "original_department_budget": 600000, "original_student_budget": 500000},
                {"id": 2, "name": "월요일 2조", "leader_name": "", "department_budget": 700000, "student_budget": 500000, "original_department_budget": 700000, "original_student_budget": 500000},
                {"id": 3, "name": "월요일 3조", "leader_name": "", "department_budget": 600000, "student_budget": 500000, "original_department_budget": 600000, "original_student_budget": 500000},
                {"id": 4, "name": "월요일 4조", "leader_name": "", "department_budget": 700000, "student_budget": 500000, "original_department_budget": 700000, "original_student_budget": 500000},
                {"id": 5, "name": "화요일 1조", "leader_name": "", "department_budget": 600000, "student_budget": 500000, "original_department_budget": 600000, "original_student_budget": 500000},
                {"id": 6, "name": "화요일 2조", "leader_name": "", "department_budget": 700000, "student_budget": 500000, "original_department_budget": 700000, "original_student_budget": 500000},
                {"id": 7, "name": "화요일 3조", "leader_name": "", "department_budget": 600000, "student_budget": 500000, "original_department_budget": 600000, "original_student_budget": 500000},
                {"id": 8, "name": "화요일 4조", "leader_name": "", "department_budget": 700000, "student_budget": 500000, "original_department_budget": 700000, "original_student_budget": 500000},
                {"id": 9, "name": "화요일 5조", "leader_name": "", "department_budget": 600000, "student_budget": 500000, "original_department_budget": 600000, "original_student_budget": 500000},
                {"id": 10, "name": "화요일 6조", "leader_name": "", "department_budget": 700000, "student_budget": 500000, "original_department_budget": 700000, "original_student_budget": 500000},
                {"id": 11, "name": "화요일 7조", "leader_name": "", "department_budget": 600000, "student_budget": 500000, "original_department_budget": 600000, "original_student_budget": 500000}
            ]
        }
        save_json(TEAMS_FILE, teams_data)
        print("✅ 초기 팀 데이터 생성 완료")
    else:
        print(f"✅ 기존 팀 데이터 보존: {len(teams_data['teams'])}개 팀")
        for team in teams_data['teams']:
            print(f"  - {team['name']}: 조장={team['leader_name'] or '미설정'}")
    
    # 다른 데이터 파일들 초기화 (없으면 빈 배열로 생성)
    for file_path, key in [(PURCHASES_FILE, 'purchases'), (MULTI_PURCHASES_FILE, 'multi_purchases'), (OTHER_REQUESTS_FILE, 'other_requests')]:
        data = load_json(file_path)
        if not data.get(key):
            data = {key: []}
            save_json(file_path, data)
    
    print("🎉 데이터 초기화 완료!")

# 라우트들
@app.route('/')
def index():
    """메인 페이지"""
    teams_data = load_json(TEAMS_FILE)
    teams = teams_data.get('teams', [])
    return render_template('index.html', teams=teams)

@app.route('/upload', methods=['POST'])
def upload():
    """구매내역 업로드"""
    try:
        team_id = int(request.form.get('team_id'))
        item_name = request.form.get('item_name', '').strip()
        price = float(request.form.get('price', 0))
        quantity = int(request.form.get('quantity', 1))
        store = request.form.get('store', '').strip()
        budget_type = request.form.get('budget_type', 'department')
        notes = request.form.get('notes', '').strip()
        
        # 파일 업로드 처리
        attachment_filename = None
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                attachment_filename = f"{uuid.uuid4()}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], attachment_filename))
        
        # 팀 정보 로드
        teams_data = load_json(TEAMS_FILE)
        team = next((t for t in teams_data['teams'] if t['id'] == team_id), None)
        if not team:
            flash('팀을 찾을 수 없습니다.', 'error')
            return redirect(url_for('index'))
        
        # 총 금액 계산
        total_amount = price * quantity
        
        # 예산 확인
        if budget_type == 'department':
            if total_amount > team['department_budget']:
                flash(f'학과지원사업 예산이 부족합니다. (잔여: {team["department_budget"]:,}원)', 'error')
                return redirect(url_for('index'))
        else:
            if total_amount > team['student_budget']:
                flash(f'학생지원사업 예산이 부족합니다. (잔여: {team["student_budget"]:,}원)', 'error')
                return redirect(url_for('index'))
        
        # 구매내역 저장
        purchases_data = load_json(PURCHASES_FILE)
        purchase = {
            'id': get_next_id(purchases_data['purchases']),
            'team_id': team_id,
            'item_name': item_name,
            'price': price,
            'quantity': quantity,
            'total_amount': total_amount,
            'store': store,
            'budget_type': budget_type,
            'notes': notes,
            'attachment_filename': attachment_filename,
            'request_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': '대기중',
            'is_approved': False
        }
        
        purchases_data['purchases'].append(purchase)
        save_json(PURCHASES_FILE, purchases_data)
        
        flash('구매내역이 성공적으로 등록되었습니다!', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        print(f"❌ 구매내역 업로드 오류: {e}")
        flash('구매내역 등록 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('index'))

@app.route('/multi_upload', methods=['POST'])
def multi_upload():
    """다중 품목 구매내역 업로드"""
    try:
        team_id = int(request.form.get('team_id'))
        store = request.form.get('store', '').strip()
        budget_type = request.form.get('budget_type', 'department')
        notes = request.form.get('notes', '').strip()
        
        # 품목 정보 파싱
        items = []
        item_names = request.form.getlist('item_name[]')
        prices = request.form.getlist('price[]')
        quantities = request.form.getlist('quantity[]')
        
        for i, item_name in enumerate(item_names):
            if item_name.strip():
                try:
                    price = float(prices[i])
                    quantity = int(quantities[i])
                    items.append({
                        'item_name': item_name.strip(),
                        'unit_price': price,
                        'quantity': quantity,
                        'total_amount': price * quantity
                    })
                except (ValueError, IndexError):
                    continue
        
        if not items:
            flash('품목 정보를 올바르게 입력해주세요.', 'error')
            return redirect(url_for('index'))
        
        # 팀 정보 로드
        teams_data = load_json(TEAMS_FILE)
        team = next((t for t in teams_data['teams'] if t['id'] == team_id), None)
        if not team:
            flash('팀을 찾을 수 없습니다.', 'error')
            return redirect(url_for('index'))
        
        # 총 금액 계산
        total_amount = sum(item['total_amount'] for item in items)
        
        # 예산 확인
        if budget_type == 'department':
            if total_amount > team['department_budget']:
                flash(f'학과지원사업 예산이 부족합니다. (잔여: {team["department_budget"]:,}원)', 'error')
                return redirect(url_for('index'))
        else:
            if total_amount > team['student_budget']:
                flash(f'학생지원사업 예산이 부족합니다. (잔여: {team["student_budget"]:,}원)', 'error')
                return redirect(url_for('index'))
        
        # 다중 구매내역 저장
        multi_purchases_data = load_json(MULTI_PURCHASES_FILE)
        multi_purchase = {
            'id': get_next_id(multi_purchases_data['multi_purchases']),
            'team_id': team_id,
            'store': store,
            'budget_type': budget_type,
            'notes': notes,
            'total_amount': total_amount,
            'items': items,
            'request_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': '대기중',
            'is_approved': False
        }
        
        multi_purchases_data['multi_purchases'].append(multi_purchase)
        save_json(MULTI_PURCHASES_FILE, multi_purchases_data)
        
        flash('다중 품목 구매내역이 성공적으로 등록되었습니다!', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        print(f"❌ 다중 구매내역 업로드 오류: {e}")
        flash('다중 품목 구매내역 등록 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('index'))

@app.route('/other_request', methods=['POST'])
def other_request():
    """기타 요청 등록"""
    try:
        team_id = int(request.form.get('team_id'))
        request_type = request.form.get('request_type', '').strip()
        description = request.form.get('description', '').strip()
        
        # 팀 정보 로드
        teams_data = load_json(TEAMS_FILE)
        team = next((t for t in teams_data['teams'] if t['id'] == team_id), None)
        if not team:
            flash('팀을 찾을 수 없습니다.', 'error')
            return redirect(url_for('index'))
        
        # 기타 요청 저장
        other_requests_data = load_json(OTHER_REQUESTS_FILE)
        other_request = {
            'id': get_next_id(other_requests_data['other_requests']),
            'team_id': team_id,
            'request_type': request_type,
            'description': description,
            'request_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': '대기중',
            'is_approved': False
        }
        
        other_requests_data['other_requests'].append(other_request)
        save_json(OTHER_REQUESTS_FILE, other_requests_data)
        
        flash('기타 요청이 성공적으로 등록되었습니다!', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        print(f"❌ 기타 요청 등록 오류: {e}")
        flash('기타 요청 등록 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('index'))

@app.route('/admin')
def admin():
    """관리자 페이지"""
    if 'admin_logged_in' not in session:
        return render_template('admin_login.html')
    
    # 데이터 로드
    teams_data = load_json(TEAMS_FILE)
    purchases_data = load_json(PURCHASES_FILE)
    multi_purchases_data = load_json(MULTI_PURCHASES_FILE)
    other_requests_data = load_json(OTHER_REQUESTS_FILE)
    
    teams = teams_data.get('teams', [])
    purchases = purchases_data.get('purchases', [])
    multi_purchases = multi_purchases_data.get('multi_purchases', [])
    other_requests = other_requests_data.get('other_requests', [])
    
    # 팀별 구매내역 통계 계산
    for team in teams:
        team['used_department'] = 0
        team['used_student'] = 0
        
        # 일반 구매내역
        for purchase in purchases:
            if purchase['team_id'] == team['id'] and purchase['is_approved']:
                if purchase['budget_type'] == 'department':
                    team['used_department'] += purchase['total_amount']
                else:
                    team['used_student'] += purchase['total_amount']
        
        # 다중 구매내역
        for multi_purchase in multi_purchases:
            if multi_purchase['team_id'] == team['id'] and multi_purchase['is_approved']:
                if multi_purchase['budget_type'] == 'department':
                    team['used_department'] += multi_purchase['total_amount']
                else:
                    team['used_student'] += multi_purchase['total_amount']
        
        # 잔여 예산 계산
        team['remaining_department'] = team['department_budget'] - team['used_department']
        team['remaining_student'] = team['student_budget'] - team['used_student']
        team['total_budget'] = team['department_budget'] + team['student_budget']
        team['total_used'] = team['used_department'] + team['used_student']
        team['total_remaining'] = team['total_budget'] - team['total_used']
        team['remaining_rate'] = (team['total_remaining'] / team['total_budget'] * 100) if team['total_budget'] > 0 else 0
    
    return render_template('admin.html', teams=teams, purchases=purchases, multi_purchases=multi_purchases, other_requests=other_requests)

@app.route('/admin_login', methods=['POST'])
def admin_login():
    """관리자 로그인"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session['admin_logged_in'] = True
        flash('관리자로 로그인되었습니다.', 'success')
        return redirect(url_for('admin'))
    else:
        flash('잘못된 사용자명 또는 비밀번호입니다.', 'error')
        return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    """로그아웃"""
    session.pop('admin_logged_in', None)
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('index'))

@app.route('/approve_purchase/<int:purchase_id>')
def approve_purchase(purchase_id):
    """구매내역 승인"""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    try:
        purchases_data = load_json(PURCHASES_FILE)
        purchase = next((p for p in purchases_data['purchases'] if p['id'] == purchase_id), None)
        
        if not purchase:
            flash('구매내역을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin'))
        
        if purchase['is_approved']:
            flash('이미 승인된 구매내역입니다.', 'info')
            return redirect(url_for('admin'))
        
        # 팀 정보 로드
        teams_data = load_json(TEAMS_FILE)
        team = next((t for t in teams_data['teams'] if t['id'] == purchase['team_id']), None)
        if not team:
            flash('팀을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin'))
        
        # 예산 확인
        if purchase['budget_type'] == 'department':
            if purchase['total_amount'] > team['department_budget']:
                flash('학과지원사업 예산이 부족합니다.', 'error')
                return redirect(url_for('admin'))
        else:
            if purchase['total_amount'] > team['student_budget']:
                flash('학생지원사업 예산이 부족합니다.', 'error')
                return redirect(url_for('admin'))
        
        # 구매내역 승인
        purchase['is_approved'] = True
        purchase['status'] = '승인됨'
        purchase['approved_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 팀 예산 차감
        if purchase['budget_type'] == 'department':
            team['department_budget'] -= purchase['total_amount']
        else:
            team['student_budget'] -= purchase['total_amount']
        
        save_json(PURCHASES_FILE, purchases_data)
        save_json(TEAMS_FILE, teams_data)
        
        flash('구매내역이 승인되었습니다.', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        print(f"❌ 구매내역 승인 오류: {e}")
        flash('구매내역 승인 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin'))

@app.route('/cancel_purchase/<int:purchase_id>')
def cancel_purchase(purchase_id):
    """구매내역 취소"""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    try:
        purchases_data = load_json(PURCHASES_FILE)
        purchase = next((p for p in purchases_data['purchases'] if p['id'] == purchase_id), None)
        
        if not purchase:
            flash('구매내역을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin'))
        
        if purchase['is_approved']:
            # 팀 정보 로드
            teams_data = load_json(TEAMS_FILE)
            team = next((t for t in teams_data['teams'] if t['id'] == purchase['team_id']), None)
            if team:
                # 예산 복원
                if purchase['budget_type'] == 'department':
                    team['department_budget'] += purchase['total_amount']
                else:
                    team['student_budget'] += purchase['total_amount']
                save_json(TEAMS_FILE, teams_data)
        
        # 구매내역 삭제
        purchases_data['purchases'] = [p for p in purchases_data['purchases'] if p['id'] != purchase_id]
        save_json(PURCHASES_FILE, purchases_data)
        
        flash('구매내역이 취소되었습니다.', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        print(f"❌ 구매내역 취소 오류: {e}")
        flash('구매내역 취소 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin'))

@app.route('/approve_multi_purchase/<int:purchase_id>')
def approve_multi_purchase(purchase_id):
    """다중 구매내역 승인"""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    try:
        multi_purchases_data = load_json(MULTI_PURCHASES_FILE)
        multi_purchase = next((p for p in multi_purchases_data['multi_purchases'] if p['id'] == purchase_id), None)
        
        if not multi_purchase:
            flash('구매내역을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin'))
        
        if multi_purchase['is_approved']:
            flash('이미 승인된 구매내역입니다.', 'info')
            return redirect(url_for('admin'))
        
        # 팀 정보 로드
        teams_data = load_json(TEAMS_FILE)
        team = next((t for t in teams_data['teams'] if t['id'] == multi_purchase['team_id']), None)
        if not team:
            flash('팀을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin'))
        
        # 예산 확인
        if multi_purchase['budget_type'] == 'department':
            if multi_purchase['total_amount'] > team['department_budget']:
                flash('학과지원사업 예산이 부족합니다.', 'error')
                return redirect(url_for('admin'))
        else:
            if multi_purchase['total_amount'] > team['student_budget']:
                flash('학생지원사업 예산이 부족합니다.', 'error')
                return redirect(url_for('admin'))
        
        # 다중 구매내역 승인
        multi_purchase['is_approved'] = True
        multi_purchase['status'] = '승인됨'
        multi_purchase['approved_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 팀 예산 차감
        if multi_purchase['budget_type'] == 'department':
            team['department_budget'] -= multi_purchase['total_amount']
        else:
            team['student_budget'] -= multi_purchase['total_amount']
        
        save_json(MULTI_PURCHASES_FILE, multi_purchases_data)
        save_json(TEAMS_FILE, teams_data)
        
        flash('다중 구매내역이 승인되었습니다.', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        print(f"❌ 다중 구매내역 승인 오류: {e}")
        flash('다중 구매내역 승인 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin'))

@app.route('/cancel_multi_purchase/<int:purchase_id>')
def cancel_multi_purchase(purchase_id):
    """다중 구매내역 취소"""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    try:
        multi_purchases_data = load_json(MULTI_PURCHASES_FILE)
        multi_purchase = next((p for p in multi_purchases_data['multi_purchases'] if p['id'] == purchase_id), None)
        
        if not multi_purchase:
            flash('구매내역을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin'))
        
        if multi_purchase['is_approved']:
            # 팀 정보 로드
            teams_data = load_json(TEAMS_FILE)
            team = next((t for t in teams_data['teams'] if t['id'] == multi_purchase['team_id']), None)
            if team:
                # 예산 복원
                if multi_purchase['budget_type'] == 'department':
                    team['department_budget'] += multi_purchase['total_amount']
                else:
                    team['student_budget'] += multi_purchase['total_amount']
                save_json(TEAMS_FILE, teams_data)
        
        # 다중 구매내역 삭제
        multi_purchases_data['multi_purchases'] = [p for p in multi_purchases_data['multi_purchases'] if p['id'] != purchase_id]
        save_json(MULTI_PURCHASES_FILE, multi_purchases_data)
        
        flash('다중 구매내역이 취소되었습니다.', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        print(f"❌ 다중 구매내역 취소 오류: {e}")
        flash('다중 구매내역 취소 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin'))

@app.route('/approve_other_request/<int:request_id>')
def approve_other_request(request_id):
    """기타 요청 승인"""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    try:
        other_requests_data = load_json(OTHER_REQUESTS_FILE)
        other_request = next((r for r in other_requests_data['other_requests'] if r['id'] == request_id), None)
        
        if not other_request:
            flash('기타 요청을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin'))
        
        if other_request['is_approved']:
            flash('이미 승인된 기타 요청입니다.', 'info')
            return redirect(url_for('admin'))
        
        # 기타 요청 승인
        other_request['is_approved'] = True
        other_request['status'] = '승인됨'
        other_request['approved_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        save_json(OTHER_REQUESTS_FILE, other_requests_data)
        
        flash('기타 요청이 승인되었습니다.', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        print(f"❌ 기타 요청 승인 오류: {e}")
        flash('기타 요청 승인 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin'))

@app.route('/cancel_other_request/<int:request_id>')
def cancel_other_request(request_id):
    """기타 요청 취소"""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    try:
        other_requests_data = load_json(OTHER_REQUESTS_FILE)
        other_request = next((r for r in other_requests_data['other_requests'] if r['id'] == request_id), None)
        
        if not other_request:
            flash('기타 요청을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin'))
        
        # 기타 요청 삭제
        other_requests_data['other_requests'] = [r for r in other_requests_data['other_requests'] if r['id'] != request_id]
        save_json(OTHER_REQUESTS_FILE, other_requests_data)
        
        flash('기타 요청이 취소되었습니다.', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        print(f"❌ 기타 요청 취소 오류: {e}")
        flash('기타 요청 취소 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin'))

@app.route('/update_team_leader', methods=['POST'])
def update_team_leader():
    """팀 조장 정보 업데이트"""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    try:
        team_id = int(request.form.get('team_id'))
        leader_name = request.form.get('leader_name', '').strip()
        
        teams_data = load_json(TEAMS_FILE)
        team = next((t for t in teams_data['teams'] if t['id'] == team_id), None)
        
        if not team:
            flash('팀을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin'))
        
        team['leader_name'] = leader_name
        save_json(TEAMS_FILE, teams_data)
        
        flash(f'{team["name"]}의 조장이 {leader_name or "미설정"}으로 변경되었습니다.', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        print(f"❌ 조장 정보 업데이트 오류: {e}")
        flash('조장 정보 업데이트 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin'))

@app.route('/view_data')
def view_data():
    """데이터베이스 보기"""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    # 모든 데이터 로드
    teams_data = load_json(TEAMS_FILE)
    purchases_data = load_json(PURCHASES_FILE)
    multi_purchases_data = load_json(MULTI_PURCHASES_FILE)
    other_requests_data = load_json(OTHER_REQUESTS_FILE)
    
    return render_template('view_data.html', 
                         teams=teams_data.get('teams', []),
                         purchases=purchases_data.get('purchases', []),
                         multi_purchases=multi_purchases_data.get('multi_purchases', []),
                         other_requests=other_requests_data.get('other_requests', []))

@app.route('/reset_database', methods=['POST'])
def reset_database():
    """데이터베이스 초기화"""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin'))
    
    try:
        # 모든 데이터 초기화
        teams_data = {
            "teams": [
                {"id": 1, "name": "월요일 1조", "leader_name": "", "department_budget": 0, "student_budget": 0, "original_department_budget": 0, "original_student_budget": 0},
                {"id": 2, "name": "월요일 2조", "leader_name": "", "department_budget": 0, "student_budget": 0, "original_department_budget": 0, "original_student_budget": 0},
                {"id": 3, "name": "월요일 3조", "leader_name": "", "department_budget": 0, "student_budget": 0, "original_department_budget": 0, "original_student_budget": 0},
                {"id": 4, "name": "월요일 4조", "leader_name": "", "department_budget": 0, "student_budget": 0, "original_department_budget": 0, "original_student_budget": 0},
                {"id": 5, "name": "화요일 1조", "leader_name": "", "department_budget": 0, "student_budget": 0, "original_department_budget": 0, "original_student_budget": 0},
                {"id": 6, "name": "화요일 2조", "leader_name": "", "department_budget": 0, "student_budget": 0, "original_department_budget": 0, "original_student_budget": 0},
                {"id": 7, "name": "화요일 3조", "leader_name": "", "department_budget": 0, "student_budget": 0, "original_department_budget": 0, "original_student_budget": 0},
                {"id": 8, "name": "화요일 4조", "leader_name": "", "department_budget": 0, "student_budget": 0, "original_department_budget": 0, "original_student_budget": 0},
                {"id": 9, "name": "화요일 5조", "leader_name": "", "department_budget": 0, "student_budget": 0, "original_department_budget": 0, "original_student_budget": 0},
                {"id": 10, "name": "화요일 6조", "leader_name": "", "department_budget": 0, "student_budget": 0, "original_department_budget": 0, "original_student_budget": 0},
                {"id": 11, "name": "화요일 7조", "leader_name": "", "department_budget": 0, "student_budget": 0, "original_department_budget": 0, "original_student_budget": 0}
            ]
        }
        
        save_json(TEAMS_FILE, teams_data)
        save_json(PURCHASES_FILE, {"purchases": []})
        save_json(MULTI_PURCHASES_FILE, {"multi_purchases": []})
        save_json(OTHER_REQUESTS_FILE, {"other_requests": []})
        
        flash('데이터베이스가 성공적으로 초기화되었습니다.', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        print(f"❌ 데이터베이스 초기화 오류: {e}")
        flash('데이터베이스 초기화 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin'))

if __name__ == '__main__':
    # 데이터 초기화 (기존 데이터 보존)
    init_data()
    print("=" * 60)
    print("🎓 예산 관리 시스템 (JSON 기반)이 시작되었습니다!")
    print("=" * 60)
    print(f"🌐 접속 주소: http://127.0.0.1:{PORT}")
    print(f"🌐 또는: http://localhost:{PORT}")
    print("=" * 60)
    print("✅ 모든 기능이 사용 가능합니다!")
    print("   - 구매내역 업로드")
    print("   - 조별 잔여금액 확인")
    print("   - 관리자 모드 (MSE3105 / KHU)")
    print("   - 데이터베이스 보기 (JSON 파일 기반)")
    print("   - 데이터 영구 보존!")
    print("=" * 60)
    
    # Render 배포를 위한 포트 설정
    import os
    port = int(os.environ.get('PORT', PORT))
    # 운영 환경에서는 디버그 모드 비활성화
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
