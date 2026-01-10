# -*- coding: utf-8 -*-
"""
Playwright UI Test for Agent Terminal
"""
import asyncio
import sys
import io

# Windows 콘솔 인코딩 처리
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright

async def test_agent_terminal():
    print("=" * 50)
    print("Agent Terminal UI Test")
    print("=" * 50)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        results = []

        try:
            # 1. 페이지 로드
            print("\n[1] Page load test...")
            await page.goto("http://localhost:8090", timeout=10000)
            title = await page.title()
            print(f"    OK - Title: {title}")
            results.append(("Page Load", True))

            # 2. 버전 표시 확인
            print("\n[2] Version display test...")
            await page.wait_for_selector("#versionDisplay", timeout=5000)
            version = await page.text_content("#versionDisplay")
            print(f"    OK - Version: {version}")
            results.append(("Version Display", True))

            # 3. 서버 상태 확인
            print("\n[3] Server status test...")
            await asyncio.sleep(2)
            status_el = await page.query_selector("#serverStatus")
            status_class = await status_el.get_attribute("class")
            status_text = await page.text_content("#serverStatus .status-text")
            is_connected = "connected" in status_class
            print(f"    {'OK' if is_connected else 'WARN'} - Status: {status_text}")
            results.append(("Server Status", is_connected))

            # 4. 헤더 버튼들 확인
            print("\n[4] Header buttons test...")
            buttons = await page.query_selector_all(".header .btn")
            print(f"    OK - Button count: {len(buttons)}")
            for btn in buttons:
                text = await btn.text_content()
                print(f"      - {text.strip()}")
            results.append(("Header Buttons", len(buttons) >= 4))

            # 5. 레이아웃 선택 확인
            print("\n[5] Layout selector test...")
            layout_select = await page.query_selector("#layoutSelect")
            options = await layout_select.query_selector_all("option")
            print(f"    OK - Layout options: {len(options)}")
            results.append(("Layout Selector", len(options) == 5))

            # 6. 에이전트 타입 선택 확인
            print("\n[6] Agent type selector test...")
            agent_select = await page.query_selector("#newAgentType")
            agent_options = await agent_select.query_selector_all("option")
            print(f"    OK - Agent types: {len(agent_options)}")
            for opt in agent_options:
                text = await opt.text_content()
                value = await opt.get_attribute("value")
                print(f"      - {value}: {text}")
            results.append(("Agent Types", len(agent_options) == 5))

            # 7. 역할 선택 확인
            print("\n[7] Role selector test...")
            role_select = await page.query_selector("#newAgentRole")
            role_options = await role_select.query_selector_all("option")
            print(f"    OK - Roles: {len(role_options)}")
            for opt in role_options:
                text = await opt.text_content()
                print(f"      - {text}")
            results.append(("Role Selector", len(role_options) == 4))

            # 8. 사이드바 섹션 확인
            print("\n[8] Sidebar sections test...")
            sidebar_sections = await page.query_selector_all(".sidebar-section")
            print(f"    OK - Sections: {len(sidebar_sections)}")
            results.append(("Sidebar Sections", len(sidebar_sections) == 3))

            # 9. 폴더 선택 모달 테스트
            print("\n[9] Folder modal test...")
            # Check if modal is already open (auto-opens on first load)
            modal = await page.query_selector("#folderModal.show")
            if not modal:
                folder_btn = await page.query_selector("text=폴더 선택")
                await folder_btn.click()
                await asyncio.sleep(0.5)
                modal = await page.query_selector("#folderModal.show")

            if modal:
                print("    OK - Folder modal opened")
                folder_items = await page.query_selector_all(".folder-item")
                print(f"    OK - Folder items: {len(folder_items)}")
                # Close modal by clicking the close button using JavaScript
                await page.evaluate("document.querySelector('#folderModal').classList.remove('show')")
                await asyncio.sleep(0.3)
                results.append(("Folder Modal", True))
            else:
                print("    FAIL - Folder modal not opened")
                results.append(("Folder Modal", False))

            # 10. 초기화 버튼 확인
            print("\n[10] Reset button test...")
            reset_btn = await page.query_selector("text=초기화")
            if reset_btn:
                print("    OK - Reset button exists")
                results.append(("Reset Button", True))
            else:
                print("    FAIL - Reset button not found")
                results.append(("Reset Button", False))

            # 11. 파일 탐색기 UI 확인
            print("\n[11] File explorer test...")
            file_explorer = await page.query_selector("#fileTree")
            work_dir = await page.query_selector("#workDirDisplay")
            # Up button has title="상위 폴더", text content is emoji
            up_btn = await page.query_selector("[title='상위 폴더']")
            if file_explorer and work_dir:
                print("    OK - File explorer UI exists")
                print(f"    - fileTree: {'found' if file_explorer else 'missing'}")
                print(f"    - workDirDisplay: {'found' if work_dir else 'missing'}")
                print(f"    - upButton: {'found' if up_btn else 'missing (optional)'}")
                results.append(("File Explorer", True))
            else:
                print("    WARN - Some file explorer elements missing")
                results.append(("File Explorer", False))

            # 12. 터미널 그리드 확인
            print("\n[12] Terminal grid test...")
            grid = await page.query_selector("#grid")
            grid_class = await grid.get_attribute("class")
            print(f"    OK - Grid class: {grid_class}")
            results.append(("Terminal Grid", "grid" in grid_class))

            # Summary
            print("\n" + "=" * 50)
            print("TEST SUMMARY")
            print("=" * 50)
            passed = sum(1 for _, r in results if r)
            failed = len(results) - passed
            for name, result in results:
                status = "PASS" if result else "FAIL"
                print(f"  [{status}] {name}")
            print(f"\nTotal: {passed}/{len(results)} passed")
            if failed == 0:
                print("All tests passed!")
            else:
                print(f"{failed} test(s) failed")

        except Exception as e:
            print(f"\nTest error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_agent_terminal())
