"""모델링: DB의 라운드 → 피처 → 학습/평가 → artifacts/.

- dataset:   DB에서 라운드 시퀀스를 읽는다 (I/O)
- features:  라운드 시작 시점에 알 수 있는 정보만으로 피처를 만든다 (순수 pandas, API와 공유)
- baselines: 비교 기준 (항상 0.5, 구매유형 룩업표)
- evaluate:  Brier / LogLoss / AUC / ECE, calibration curve
- train:     분할 → 학습 → 보정 → 평가 → 직렬화
"""
