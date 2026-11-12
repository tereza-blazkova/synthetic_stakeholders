<!--
RECONSTRUCTED. The provisional specification handed to the human participants
was not preserved. Built from protocol section 9 and main.tex 3f / "From survey
responses to selection rules". Every {placeholder} is filled by code with the
median of THIS panel's endline answers (Not sure / Prefer not to answer / blank
excluded; ties resolved by count, then toward the more restrictive category).
Only Q3-Q5 are included: the paper states the intervention questions were not
part of the specification participants assessed.
-->

# Provisional model specification

This specification reflects the **middle-ground responses from the group's
endline survey**: for each question, the median answer of the group.

Please keep in mind:

- This specification represents a **majority-supported scenario, not a final or
  binding decision**.
- The purpose is to understand **your individual reaction**, including any
  reservations and objections.
- **All positions, including disagreement, are legitimate and important.**
- Your assessment is anonymous.

"An improvement" means correctly identifying more students who are experiencing
academic difficulties out of 100 such students, while the number of students
incorrectly flagged stays about the same.

## Data the model may use

The model starts from course credits earned. Each further data type is added
only under this condition:

| Data added | Condition |
|---|---|
| Course performance (grades, passed/failed and registered courses) | {Q3.2} |
| Admissions and enrolment data (high-school GPA, programme, school) | {Q3.3} |
| Absalon online course activity (page views, late submissions) | {Q3.4} |

## Sensitive data

| Data type | If it improves identification | If it only improves fairness |
|---|---|---|
| Age | {Q3.5.age} | {Q3.6.age} |
| Gender | {Q3.5.gender} | {Q3.6.gender} |
| Nationality | {Q3.5.nationality} | {Q3.6.nationality} |
| Disability-related information | {Q3.5.disability} | {Q3.6.disability} |
| Race/ethnicity | {Q3.5.race_ethnicity} | {Q3.6.race_ethnicity} |
| First-generation college student status | {Q3.5.first_gen} | {Q3.6.first_gen} |
| Financial aid status | {Q3.5.financial_aid} | {Q3.6.financial_aid} |

## Explainability

The starting point is a single clear rule (very high explainability). A less
explainable model is used only under this condition, compared to the next more
explainable level:

| Explainability level | Condition |
|---|---|
| High (few clearly defined factors) | {Q4.1.high} |
| Moderate (many additive factors) | {Q4.1.moderate} |
| Low (limited, case-specific explanations) | {Q4.1.low} |
| Very low (no meaningful case-specific explanation) | {Q4.1.very_low} |

## Fairness

- To make the model work equally well across student groups, the group accepts:
  {Q5.1}.
- What should be equal across student groups: {Q5.2}.
