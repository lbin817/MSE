# Wix 도메인 연결 설정 가이드

## 1. Wix 도메인 관리
1. **Wix 대시보드** 접속
2. **도메인** → **lbinlab.com** 선택
3. **DNS 설정** 클릭

## 2. CNAME 레코드 추가
다음 CNAME 레코드를 추가하세요:

### Vercel 사용 시:
```
Type: CNAME
Name: budget
Value: cname.vercel-dns.com
TTL: 3600
```

### Netlify 사용 시:
```
Type: CNAME
Name: budget
Value: your-site-name.netlify.app
TTL: 3600
```

### Railway 사용 시:
```
Type: CNAME
Name: budget
Value: your-app.railway.app
TTL: 3600
```

## 3. DNS 전파 확인
- DNS 변경사항이 전파되는데 24-48시간 소요
- 온라인 DNS 체커로 확인 가능:
  - https://dnschecker.org
  - https://whatsmydns.net

## 4. SSL 인증서
- 대부분의 호스팅 서비스에서 자동으로 SSL 인증서 발급
- `https://budget.lbinlab.com`으로 접속 가능

## 5. 서브도메인 옵션
다음과 같은 서브도메인을 사용할 수 있습니다:
- `budget.lbinlab.com` (예산 관리)
- `mse.lbinlab.com` (MSE 프로젝트)
- `admin.lbinlab.com` (관리자 페이지)
- `app.lbinlab.com` (앱 메인)

## 6. 메인 도메인 리다이렉트
메인 도메인(`lbinlab.com`)을 서브도메인으로 리다이렉트:
```
Type: A
Name: @
Value: 192.0.2.1 (호스팅 서비스 IP)
```

또는

```
Type: CNAME
Name: @
Value: budget.lbinlab.com
```

