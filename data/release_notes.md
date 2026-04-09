# SmartRecommend v2.0 — Release Notes

## Feature Overview
SmartRecommend v2.0 replaces the legacy collaborative-filtering recommendation engine with a 
real-time ML inference pipeline. The new engine uses a transformer-based model served via a 
new microservice (`recommend-svc`) to generate personalised product recommendations.

## Key Changes
- Replaced batch recommendation job (ran every 6h) with real-time inference (<200ms target)
- New `recommend-svc` microservice deployed on Kubernetes (3 replicas, auto-scaling enabled)
- Recommendation UI redesigned: horizontal scroll carousel replaces vertical list
- Added "Why recommended" explainability tooltip
- Payment flow updated to pre-fill recommended item details on checkout

## Rollout Strategy
- Day 1–3: 10% of users (canary)
- Day 4–7: 50% of users
- Day 8+: 100% of users (current state)

## Known Issues at Launch
1. **Model cold-start latency**: First inference after pod restart can take 2–4s. Mitigation: 
   keep-alive probes configured but not yet validated under full load.
2. **Out-of-stock items**: Recommendation model was trained on catalogue snapshot from 3 weeks 
   prior. ~8% of recommended SKUs may be out of stock. Fix scheduled for v2.1.
3. **Android WebView crash**: Known crash on Android 10 devices using WebView < 89. 
   Affects ~12% of Android user base. Workaround not yet shipped.
4. **Payment service integration**: The new checkout pre-fill relies on `payment-svc` v3.2. 
   Some users on legacy payment tokens (issued before 2024-06-01) may see failures. 
   Estimated affected users: ~6% of active payers.
5. **Auto-scaling lag**: `recommend-svc` auto-scaling triggers at 70% CPU but scale-up takes 
   ~90 seconds, causing latency spikes during traffic surges.

## Rollback Plan
- Feature flag `SMARTRECOMMEND_V2_ENABLED` can disable v2 engine instantly (returns to v1)
- Full rollback (revert deployment): ~15 minutes via `kubectl rollout undo`
- Data: No schema migrations; rollback is non-destructive
