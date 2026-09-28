"""ETL: Kaggle VCT CSV → PostgreSQL.

단계별 모듈을 나눠 '무엇이 DB 없이 테스트 가능한가'를 분명히 한다.
- sources:   원본 파일 위치 탐색과 읽기 (I/O만)
- normalize: 값 정규화 (금액 문자열, 대회명 표기 차이)
- sides:     라운드 승리 방식으로 공격/수비 진영 역산
- transform: matches / map_games / rounds 테이블 모양으로 변환 (순수 pandas)
- load:      PostgreSQL 멱등 적재 (upsert)
"""
