# 배포 가이드

## GitHub + Render 배포 방법

### 1. GitHub 저장소 생성 및 업로드

#### 필요한 파일들:
```
MSE/
├── simple_flask.py          # 메인 Flask 애플리케이션
├── config.py               # 설정 파일
├── requirements.txt        # Python 패키지 목록
├── render.yaml            # Render 배포 설정
├── Procfile               # Render 프로세스 설정
├── runtime.txt            # Python 버전 설정
├── .gitignore             # Git 무시 파일 목록
├── README.md              # 프로젝트 설명서
├── DEPLOYMENT.md          # 배포 가이드 (이 파일)
└── templates/             # HTML 템플릿 폴더
    ├── base.html
    ├── index.html
    ├── upload.html
    ├── check_balance.html
    ├── admin_login.html
    └── admin.html
```

#### GitHub 업로드 단계:
1. GitHub에서 새 저장소 생성
2. 로컬에서 Git 초기화:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Budget Management System"
   git branch -M main
   git remote add origin https://github.com/[사용자명]/[저장소명].git
   git push -u origin main
   ```

### 2. Render 배포 설정

#### Render 계정 생성:
1. [render.com](https://render.com) 접속
2. GitHub 계정으로 로그인
3. "New +" 버튼 클릭 → "Web Service" 선택

#### 배포 설정:
1. **Connect Repository**: GitHub 저장소 연결
2. **Name**: `budget-management-system` (또는 원하는 이름)
3. **Environment**: `Python 3`
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `python simple_flask.py`
6. **Plan**: Free (무료 플랜)

#### 환경 변수 설정 (권장):
- `SECRET_KEY`: `your-very-secure-secret-key-here` (보안을 위해 강력한 키 사용)
- `ADMIN_USERNAME`: `MSE3105` (기본값, 변경 가능)
- `ADMIN_PASSWORD`: `KHU` (기본값, 보안을 위해 변경 권장)
- `FLASK_ENV`: `production`
- `FLASK_DEBUG`: `false`

### 3. 배포 후 확인사항

#### 접속 URL:
- Render에서 제공하는 URL로 접속
- 예: `https://budget-management-system.onrender.com`

#### 기능 테스트:
1. **홈페이지**: 메인 화면 확인
2. **구매내역 업로드**: 폼 입력 테스트
3. **조별 잔여금액 확인**: 조 정보 입력 테스트
4. **관리자 모드**: MSE3105/KHU 로그인 테스트

### 4. 주의사항

#### 무료 플랜 제한:
- 서버가 15분간 비활성화되면 자동으로 슬립 모드
- 첫 접속 시 약간의 지연 시간 발생
- 월 750시간 제한

#### 데이터베이스:
- SQLite 파일 기반 데이터베이스 사용
- 서버 재시작 시 데이터 유지됨
- 대용량 데이터의 경우 PostgreSQL 권장

#### 보안:
- 현재 IP 제한 비활성화 상태
- 필요시 `config.py`에서 IP 제한 활성화 가능
- 관리자 계정 보안 강화 권장

### 5. 문제 해결

#### 배포 실패 시:
1. **Build Log** 확인
2. **Requirements.txt** 패키지 버전 확인
3. **Python 버전** 호환성 확인

#### 접속 불가 시:
1. **Service Log** 확인
2. **환경 변수** 설정 확인
3. **포트 설정** 확인

### 6. 업데이트 방법

#### 코드 수정 후:
```bash
git add .
git commit -m "Update: 기능 개선"
git push origin main
```
- Render에서 자동으로 재배포됨

### 7. 도메인 연결 (선택사항)

#### 커스텀 도메인:
1. Render 대시보드에서 "Custom Domains" 설정
2. DNS 설정에서 CNAME 레코드 추가
3. SSL 인증서 자동 발급

---

## 지원

문제가 발생하면 다음을 확인하세요:
- [Render 문서](https://render.com/docs)
- [Flask 문서](https://flask.palletsprojects.com/)
- 프로젝트 README.md 파일
