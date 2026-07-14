# DeepEval Report

Cases recorded this session: 15

| Test | Metric | Score | Target | Status |
|------|--------|-------|--------|--------|
| test_faq_cases[test_faq_pricing_question_grounded] | Answer Relevancy | 0.500 | ≥ 0.70 | ❌ |
| test_faq_cases[test_faq_pricing_question_grounded] | Faithfulness | 1.000 | ≥ 0.70 | ✅ |
| test_faq_cases[test_faq_clinic_info_question_grounded] | Answer Relevancy | 1.000 | ≥ 0.70 | ✅ |
| test_faq_cases[test_faq_clinic_info_question_grounded] | Faithfulness | 1.000 | ≥ 0.70 | ✅ |
| test_faq_cases[test_faq_out_of_scope_question_not_fabricated] | NoFabricatedPolicy [GEval] | 1.000 | ≥ 0.70 | ✅ |
| test_faq_cases[test_faq_surgery_pricing_question_grounded] | Answer Relevancy | 0.500 | ≥ 0.70 | ❌ |
| test_faq_cases[test_faq_surgery_pricing_question_grounded] | Faithfulness | 1.000 | ≥ 0.70 | ✅ |
| test_faq_cases[test_faq_specialties_overview_question_grounded] | Answer Relevancy | 0.375 | ≥ 0.70 | ❌ |
| test_faq_cases[test_faq_specialties_overview_question_grounded] | Faithfulness | 1.000 | ≥ 0.70 | ✅ |
| test_faq_cases[test_faq_cancellation_policy_not_fabricated] | NoFabricatedCancellationPolicy [GEval] | 1.000 | ≥ 0.70 | ✅ |
| test_symptom_cases[test_symptom_medical_guide_question_grounded] | Answer Relevancy | 0.750 | ≥ 0.70 | ✅ |
| test_symptom_cases[test_symptom_medical_guide_question_grounded] | Faithfulness | 1.000 | ≥ 0.70 | ✅ |
| test_symptom_cases[test_symptom_routes_to_real_doctor_for_covered_specialty] | RoutesToRealDaLieuDoctor [GEval] | 1.000 | ≥ 0.70 | ✅ |
| test_symptom_cases[test_symptom_routes_to_real_doctor_for_tim_mach_specialty] | RoutesToRealTimMachDoctor [GEval] | 1.000 | ≥ 0.70 | ✅ |
| test_symptom_cases[test_symptom_medical_guide_question_grounded_heart_valve] | Answer Relevancy | 0.750 | ≥ 0.70 | ✅ |
| test_symptom_cases[test_symptom_medical_guide_question_grounded_heart_valve] | Faithfulness | 1.000 | ≥ 0.70 | ✅ |
| test_symptom_cases[test_symptom_routes_to_real_doctor_for_tai_mui_hong_specialty] | RoutesToRealTaiMuiHongDoctor [GEval] | 1.000 | ≥ 0.70 | ✅ |
| test_symptom_cases[test_symptom_routes_to_real_doctor_for_tieu_hoa_specialty] | RoutesToRealTieuHoaDoctor [GEval] | 0.800 | ≥ 0.70 | ✅ |
| test_booking_cases[test_booking_proposes_only_real_available_slot] | FaithfulToCheckAvailableSlots [GEval] | 1.000 | ≥ 0.70 | ✅ |
| test_booking_cases[test_booking_confirms_before_create_then_creates_real_booking] | FaithfulToBookingOutcome [GEval] | 1.000 | ≥ 0.70 | ✅ |
| test_booking_cases[test_booking_non_work_day_no_fabricated_slots] | NoFabricatedSlotsOnNonWorkDay [GEval] | 1.000 | ≥ 0.70 | ✅ |
