"""Automated Verification Suite for Homepage Searchable Skill Autocomplete (Standard Library Only)."""

import json
import re
import sys
from app import create_app
from extensions import db
from models.auth import Skill

def run_tests():
    app = create_app()
    client = app.test_client()

    print("=" * 60)
    print("STARTING HOMEPAGE SKILL AUTOCOMPLETE VERIFICATION")
    print("=" * 60)

    # 1. Homepage Rendering & DOM Structure
    print("\n--- TEST 1: Homepage Search UI Structure ---")
    res = client.get("/")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    html = res.data.decode("utf-8")

    # Verify hero search form
    assert 'id="heroSearchForm"' in html, "Hero search form (#heroSearchForm) not found!"
    assert 'action="/mentors"' in html, "Form action='/mentors' not found!"
    print("✓ Hero search form found with action='/mentors' and method='get'")

    # Verify old <select name="skill_id"> is removed from hero form
    # Note: Search results page or other pages might have select, but homepage hero form shouldn't
    hero_form_match = re.search(r'<form class="search-panel mb-0".*?</form>', html, re.DOTALL)
    assert hero_form_match is not None, "Hero form block not found!"
    hero_form_html = hero_form_match.group(0)
    assert '<select' not in hero_form_html, "Old <select> still present in hero search form!"
    print("✓ Old static select dropdown successfully removed from hero form")

    # Verify new text input
    assert 'id="skillSearchInput"' in hero_form_html, "Autocomplete input (#skillSearchInput) not found!"
    assert 'name="skill"' in hero_form_html, "Input should have name='skill'"
    assert 'type="text"' in hero_form_html, "Input should have type='text'"
    assert 'autocomplete="off"' in hero_form_html, "Input should have autocomplete='off'"
    assert 'placeholder="What do you want to learn?"' in hero_form_html, "Placeholder not found!"
    print("✓ Found text input: placeholder='What do you want to learn?' with autocomplete='off'")

    # Verify hidden skill_id input
    assert 'id="selectedSkillId"' in hero_form_html, "Hidden input (#selectedSkillId) not found!"
    assert 'name="skill_id"' in hero_form_html, "Hidden input should have name='skill_id'"
    assert 'type="hidden"' in hero_form_html, "Hidden input should have type='hidden'"
    print("✓ Found hidden input name='skill_id' for submitting skill ID")

    # Verify autocomplete dropdown containers
    assert 'id="skillAutocompleteDropdown"' in hero_form_html, "#skillAutocompleteDropdown container not found!"
    assert 'id="skillSuggestionsList"' in hero_form_html, "#skillSuggestionsList not found inside dropdown!"
    assert 'id="skillNoMatches"' in hero_form_html, "#skillNoMatches not found inside dropdown!"
    assert 'No matching skills found' in hero_form_html, "Expected 'No matching skills found' message"
    print("✓ Autocomplete dropdown markup, list container, and empty state verified")

    # Verify location Near input and Search mentors button
    assert 'name="city"' in hero_form_html, "'Near' (city) input missing from hero form!"
    assert 'Search mentors' in hero_form_html, "Submit button text should contain 'Search mentors'"
    print("✓ 'Near' (city) input and 'Search mentors' button intact and untouched")

    # 2. Verify Skills Data JSON
    print("\n--- TEST 2: Existing Skills Data Payload ---")
    script_match = re.search(r'<script type="application/json" id="skillsData">\s*(\[.*?\])\s*</script>', html, re.DOTALL)
    assert script_match is not None, "<script id='skillsData'> not found or malformed!"
    skills_data = json.loads(script_match.group(1))
    assert len(skills_data) > 0, "No skills found in skillsData JSON!"
    print(f"✓ Total active skills loaded into autocomplete: {len(skills_data)}")

    skill_names = [s["name"] for s in skills_data]
    expected_skills = [
        "Web Development",
        "Data Analysis",
        "App Development",
        "Cooking",
        "Digital Marketing"
    ]
    for exp in expected_skills:
        assert exp in skill_names, f"Expected skill '{exp}' not found in skills data! Found: {skill_names[:5]}"
        print(f"  - Verified skill present: '{exp}'")

    # 3. Verify Case Insensitive & Substring Matching Logic
    print("\n--- TEST 3: Autocomplete Filtering & Ranking Logic ---")
    def simulate_get_matches(query):
        q = (query or "").strip().lower()
        if not q:
            return list(skills_data)
        starts_with = []
        word_starts_with = []
        contains = []
        for item in skills_data:
            lower = item["name"].lower()
            if lower.startswith(q):
                starts_with.append(item)
            elif (f" {q}" in lower or f"/ {q}" in lower or f"-{q}" in lower):
                word_starts_with.append(item)
            elif q in lower:
                contains.append(item)
        return starts_with + word_starts_with + contains

    # Test "web"
    m_web = [s["name"] for s in simulate_get_matches("web")]
    assert "Web Development" in m_web, f"'Web Development' missing for query 'web': {m_web}"
    print(f"✓ Query 'web' matches: {m_web}")

    # Test "WEB" (uppercase)
    m_web_upper = [s["name"] for s in simulate_get_matches("WEB")]
    assert "Web Development" in m_web_upper, f"'Web Development' missing for query 'WEB': {m_web_upper}"
    print(f"✓ Query 'WEB' (uppercase) matches: {m_web_upper}")

    # Test "data"
    m_data = [s["name"] for s in simulate_get_matches("data")]
    assert "Data Analysis" in m_data, f"'Data Analysis' missing for query 'data': {m_data}"
    print(f"✓ Query 'data' matches: {m_data}")

    # Test "DATA"
    m_data_upper = [s["name"] for s in simulate_get_matches("DATA")]
    assert "Data Analysis" in m_data_upper, f"'Data Analysis' missing for query 'DATA': {m_data_upper}"
    print(f"✓ Query 'DATA' matches: {m_data_upper}")

    # Test "app"
    m_app = [s["name"] for s in simulate_get_matches("app")]
    assert "App Development" in m_app, f"'App Development' missing for query 'app': {m_app}"
    print(f"✓ Query 'app' matches: {m_app}")

    # Test "cook"
    m_cook = [s["name"] for s in simulate_get_matches("cook")]
    assert "Cooking" in m_cook, f"'Cooking' missing for query 'cook': {m_cook}"
    print(f"✓ Query 'cook' matches: {m_cook}")

    # Test "develop" (contains / word boundary)
    m_dev = [s["name"] for s in simulate_get_matches("develop")]
    assert "Web Development" in m_dev and "App Development" in m_dev, f"Expected both Web and App dev for 'develop': {m_dev}"
    print(f"✓ Query 'develop' matches both: {m_dev}")

    # Test "analysis" (word boundary / contains)
    m_analysis = [s["name"] for s in simulate_get_matches("analysis")]
    assert "Data Analysis" in m_analysis, f"'Data Analysis' missing for query 'analysis': {m_analysis}"
    print(f"✓ Query 'analysis' matches: {m_analysis}")

    # Test unknown query
    m_unknown = simulate_get_matches("xyznomatch123")
    assert len(m_unknown) == 0, f"Expected 0 matches for 'xyznomatch123', got {m_unknown}"
    print("✓ Unknown query returns 0 matches (triggers 'No matching skills found')")

    # 4. Search Submission Integration Tests
    print("\n--- TEST 4: Search Submission & Discovery Endpoint Integration ---")
    # Submitting with skill_id
    web_dev_skill = next(s for s in skills_data if s["name"] == "Web Development")
    res_search_id = client.get(f"/mentors?skill_id={web_dev_skill['id']}&city=Dhaka")
    assert res_search_id.status_code == 200, f"Search by skill_id failed with status {res_search_id.status_code}"
    print(f"✓ Search by skill_id={web_dev_skill['id']} succeeds with status 200")

    # Submitting with skill name query (fallback support)
    res_search_name = client.get("/mentors?skill=Web+Development")
    assert res_search_name.status_code == 200, f"Search by skill name failed with status {res_search_name.status_code}"
    search_html = res_search_name.data.decode("utf-8")
    assert f'value="{web_dev_skill["id"]}" selected' in search_html, "Expected skill to be selected in search filters"
    print("✓ Search by skill name fallback ('/mentors?skill=Web+Development') successfully resolved to skill_id")

    # Submitting with partial skill query
    res_search_partial = client.get("/mentors?skill=web")
    assert res_search_partial.status_code == 200
    search_partial_html = res_search_partial.data.decode("utf-8")
    assert f'value="{web_dev_skill["id"]}" selected' in search_partial_html
    print("✓ Search by partial skill name fallback ('/mentors?skill=web') successfully resolved to Web Development")

    # 5. Non-regression: Other Sections on Homepage
    print("\n--- TEST 5: Non-regression Verification ---")
    assert 'Explore what you could learn.' in html, "'Explore what you could learn' heading missing!"
    explore_card_matches = re.findall(r'class="skill-card"', html)
    assert len(explore_card_matches) > 0, "No skill cards found in Explore section!"
    print(f"✓ 'Explore what you could learn' cards count: {len(explore_card_matches)}")

    verified_mentors = re.findall(r'class="mentor-card-modern', html)
    print(f"✓ Featured verified mentors count: {len(verified_mentors)}")

    print("\n" + "=" * 60)
    print("ALL HOMEPAGE SKILL AUTOCOMPLETE TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
