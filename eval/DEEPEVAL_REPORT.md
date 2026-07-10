# DeepEval Report

Cases recorded this session: 9

| Test | Metric | Score | Target | Status |
|------|--------|-------|--------|--------|
| test_faq_pricing_question_grounded | Answer Relevancy | 1.000 | ≥ 0.70 | ✅ |
| test_faq_pricing_question_grounded | Faithfulness | 1.000 | ≥ 0.70 | ✅ |
| test_faq_clinic_info_question_grounded | Answer Relevancy | 1.000 | ≥ 0.70 | ✅ |
| test_faq_clinic_info_question_grounded | Faithfulness | 1.000 | ≥ 0.70 | ✅ |
| test_faq_out_of_scope_question_not_fabricated | NoFabricatedPolicy [GEval] | 0.700 | ≥ 0.70 | ✅ |
| test_symptom_medical_guide_question_grounded | Answer Relevancy | 1.000 | ≥ 0.70 | ✅ |
| test_symptom_medical_guide_question_grounded | Faithfulness | 1.000 | ≥ 0.70 | ✅ |
| test_symptom_routes_to_real_doctor_for_covered_specialty | RoutesToRealDaLieuDoctor [GEval] | 1.000 | ≥ 0.70 | ✅ |
| test_symptom_does_not_invent_doctor_for_uncovered_specialty | NoFabricatedCardiologist [GEval] | 1.000 | ≥ 0.70 | ✅ |
| test_booking_proposes_only_real_available_slot | FaithfulToCheckAvailableSlots [GEval] | 1.000 | ≥ 0.70 | ✅ |
| test_booking_confirms_before_create_then_creates_real_booking | FaithfulToBookingOutcome [GEval] | 1.000 | ≥ 0.70 | ✅ |
| test_booking_non_work_day_no_fabricated_slots | NoFabricatedSlotsOnNonWorkDay [GEval] | 1.000 | ≥ 0.70 | ✅ |
