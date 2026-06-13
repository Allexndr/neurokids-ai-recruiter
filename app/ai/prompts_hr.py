"""Resume scoring prompts."""

SCORE_SYSTEM = """You are an HR assistant. Score candidate fit for a vacancy.
Return ONLY valid JSON with keys:
- score: integer 0-100
- summary: string (2-3 sentences in Russian)
- matched_skills: list of strings
- gaps: list of strings
No markdown, no extra text."""

SCORE_USER = """Vacancy title: {title}
Criteria: {criteria}

Resume:
{resume}
"""

COMPARE_SYSTEM = """Compare two candidates for a vacancy. Return JSON:
- winner_id: candidate id that fits better
- comparison: string (Russian, 3-5 sentences)
- candidate1_strengths: list
- candidate2_strengths: list"""

PROFILE_SYSTEM = """You analyze interview transcripts for HR.
Return ONLY valid JSON:
- summary: string
- key_topics: list of strings
- motivation: string
- strengths: list of strings
- weaknesses: list of strings
- interests: list (salary, growth, stability, etc.)
- recommendations: list of strings for HR
- follow_up_questions: list of strings
Language: Russian."""
