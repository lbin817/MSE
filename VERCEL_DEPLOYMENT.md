# Vercel 배포 가이드

## 1. Vercel 계정 생성
1. https://vercel.com 접속
2. GitHub 계정으로 로그인
3. 무료 계정 생성

## 2. 프로젝트 배포
1. **Import Project** 클릭
2. GitHub 저장소 선택
3. **Framework Preset**: Other
4. **Root Directory**: ./
5. **Build Command**: (비워둠)
6. **Output Directory**: (비워둠)

## 3. 환경 변수 설정
Vercel 대시보드에서 다음 환경 변수 추가:

| Key | Value |
|-----|-------|
| `SECRET_KEY` | `your-very-secure-secret-key-here` |
| `ADMIN_USERNAME` | `MSE3105` |
| `ADMIN_PASSWORD` | `your-secure-password` |

## 4. 도메인 연결
1. **Settings** → **Domains**
2. **Add Domain** 클릭
3. `budget.lbinlab.com` 입력
4. DNS 설정 안내에 따라 Wix에서 CNAME 설정

## 5. Wix DNS 설정
1. Wix 대시보드 → 도메인 관리
2. DNS 설정 → CNAME 레코드 추가:
   - **Name**: `budget`
   - **Value**: `cname.vercel-dns.com`
   - **TTL**: `3600`

## 6. 배포 완료
- Vercel에서 자동으로 HTTPS 인증서 발급
- 도메인 연결 완료 후 `https://budget.lbinlab.com` 접속 가능

## 장점
- ✅ 무료 호스팅
- ✅ 슬립 모드 없음
- ✅ 자동 HTTPS
- ✅ 글로벌 CDN
- ✅ 자동 배포 (GitHub 푸시 시)

