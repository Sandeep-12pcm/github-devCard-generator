import asyncio
import json
from mcp_server import scrape_github, analyze_profile, generate_card_html

async def main():
    print("Step 1: Calling scrape_github with username 'torvalds'...")
    try:
        github_data = await scrape_github("torvalds")
        print("[OK] scrape_github completed successfully!")
        print(f"   Name: {github_data.get('name')}")
        print(f"   Location: {github_data.get('location')}")
        print(f"   Followers: {github_data.get('followers')}")
        print(f"   Languages: {list(github_data.get('languages', {}).keys())[:5]}")
    except Exception as e:
        print(f"[FAIL] scrape_github failed: {str(e)}")
        return

    print("\nStep 2: Passing scraped data to analyze_profile...")
    try:
        analysis = await analyze_profile(github_data)
        print("[OK] analyze_profile completed successfully!")
        print(f"   Theme: {analysis.get('card_theme')}")
        print(f"   Skills: {analysis.get('top_skills')}")
        print(f"   Fun Fact: {analysis.get('fun_fact')}")
    except Exception as e:
        print(f"[FAIL] analyze_profile failed: {str(e)}")
        return

    print("\nStep 3: Generating HTML card using generate_card_html...")
    try:
        html_card = await generate_card_html("torvalds", github_data, analysis)
        print("[OK] generate_card_html completed successfully!")
        print(f"   Generated Card Size: {len(html_card)} characters")
    except Exception as e:
        print(f"[FAIL] generate_card_html failed: {str(e)}")
        return

    print("\n================ TEST RESULTS ================")
    print(f"Card Theme:     {analysis.get('card_theme')}")
    print(f"Developer Vibe: {analysis.get('developer_vibe')}")
    print("==============================================")

if __name__ == "__main__":
    asyncio.run(main())
