from celery import shared_task
from forum.models import User, GradebookSnapshot
import logging
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
from django.utils.html import strip_tags
from django.http import HttpRequest
import django
import tempfile
import shutil
import concurrent.futures
import traceback
import gc
import uuid
import os
import platform

logger = logging.getLogger(__name__)

def get_memory_optimized_chrome_options():
    """
    Get Chrome options optimized for low memory usage and crash prevention
    
    Returns:
        Options: Configured Chrome options
    """
    chrome_options = Options()
    
    # Check if running locally vs Heroku to prevent segfaults in local dev
    is_heroku = os.environ.get('CHROME_BIN') is not None
    
    if is_heroku:
        chrome_options.add_argument("--headless=new")  # Force headless mode for production
    else:
        # Local development - avoid headless to prevent segfaults
        logger.info("Running locally - GUI mode enabled to prevent segmentation faults")
    
    # Essential crash prevention flags
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # Critical flags to prevent segfaults in fork processes
    # Only add zygote/single-process flags on Linux/Heroku where forking issues are common.
    # These flags are known to cause Chrome to crash or close the DevTools connection on macOS.
    try:
        system_name = platform.system().lower()
    except Exception:
        system_name = ''

    add_isolation_flags = False
    # If running on Heroku (CHROME_BIN set) or on Linux, enable these isolation flags
    if os.environ.get('CHROME_BIN') is not None or system_name == 'linux':
        add_isolation_flags = True

    if add_isolation_flags:
        chrome_options.add_argument("--no-zygote")  # Disable zygote process
        chrome_options.add_argument("--single-process")  # Force single process mode
    else:
        logger.debug(f"Skipping --no-zygote/--single-process flags on platform={system_name}")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    
    # Disable problematic features that can cause crashes
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-default-apps")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--disable-translate")
    chrome_options.add_argument("--disable-features=TranslateUI")
    chrome_options.add_argument("--disable-ipc-flooding-protection")
    
    # Memory and stability
    # chrome_options.add_argument("--max_old_space_size=4096")
    # chrome_options.add_argument("--no-first-run")
    # chrome_options.add_argument("--no-default-browser-check")
    
    # Only disable images if not causing redirect issues
    # chrome_options.add_argument("--blink-settings=imagesEnabled=false")

    # Set a safer page load strategy (normal) to ensure redirects complete
    chrome_options.set_capability("pageLoadStrategy", "normal")
    
    # Configure Chrome binary location for Heroku
    chrome_bin = os.environ.get('CHROME_BIN')
    if chrome_bin:
        chrome_options.binary_location = chrome_bin
        logger.info(f"Using Chrome binary from environment: {chrome_bin}")
    
    return chrome_options

def create_webdriver_with_cleanup():
    """
    Create a WebDriver with proper cleanup handling using enhanced isolation
    
    Returns:
        tuple: (driver, temp_user_data_dir)
    """
    # Create a unique temporary user-data-dir per run to avoid conflicts
    # when multiple WebDriver instances are created concurrently.
    chrome_options = get_memory_optimized_chrome_options()

    temp_user_data_dir = None
    try:
        temp_user_data_dir = tempfile.mkdtemp(prefix='chrome_user_data_')
        # Ensure directory was created
        if temp_user_data_dir and os.path.isdir(temp_user_data_dir):
            chrome_options.add_argument(f"--user-data-dir={temp_user_data_dir}")
    except Exception:
        # If creation fails, proceed without explicitly setting user-data-dir.
        temp_user_data_dir = None

    chrome_options.add_argument("--incognito")

    # Create ChromeDriver service
    from selenium.webdriver.chrome.service import Service
    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_window_size(1000, 1000)
    logger.info(f"Created WebDriver using temp user-data-dir: {temp_user_data_dir}")
    return driver, temp_user_data_dir

def get_decrypted_wolfnet_password(user_email):
    """
    Args:
        user_email (str): User's school email address
    
    Returns:
        str: Decrypted WolfNet password or None if not found
    """
    user = User.objects.get(school_email=user_email)
    profile = user.userprofile
    return profile.get_decrypted_wolfnet_password()

def compare_assignments(old_assignments, new_assignments):
    """
    Args:
        old_assignments (list): Previous assignment data
        new_assignments (list): Current assignment data
    
    Returns:
        list: List of changes detected between old and new assignments
    """
    changes = []
    old_map = {a["assignment_id"]: a for a in old_assignments}
    for new_a in new_assignments:
        aid = new_a["assignment_id"]
        old_a = old_map.get(aid)
        if not old_a:
            changes.append({"type": "new", "assignment": new_a})
            continue

        old_skills = {s["skill_id"]: s for s in old_a.get("skills", [])}
        for s in new_a["skills"]:
            old_s = old_skills.get(s["skill_id"])
            if not old_s or s["rating"] != old_s.get("rating") or s["rating_desc"] != old_s.get("rating_desc"):
                changes.append({"type": "skill_changed", "assignment": new_a, "skill": s})

        if new_a.get("points_earned") != old_a.get("points_earned") or new_a.get("max_points") != old_a.get("max_points"):
            changes.append({"type": "points_changed", "assignment": new_a})
        if new_a.get("comment") != old_a.get("comment"):
            changes.append({"type": "comment_changed", "assignment": new_a})
    return changes

def login_to_wolfnet(user_email, driver, wait, password=None):
    """
    Args:
        user_email (str): User's school email address
        driver: Selenium WebDriver instance
        wait: WebDriverWait instance
        password (str, optional): WolfNet password, uses stored password if None
    
    Returns:
        dict: {"success": bool, "error": str, "error_type": str} or {"success": True} if successful
    """
    LOGIN_URL = "https://wpga.myschoolapp.com/"
    
    if password:
        PASSWORD = password
    else:
        PASSWORD = get_decrypted_wolfnet_password(user_email)
        if not PASSWORD:
            logger.error(f"No Wolfnet password found for {user_email}. Cannot login.")
            return {"success": False, "error": "No WolfNet password found", "error_type": "no_password"}
    
    try:
        logger.info(f"Navigating to login page for {user_email}")
        driver.get(LOGIN_URL)
        logger.info(f"Current URL after navigation: {driver.current_url}")
        logger.debug(f"Page source after navigation:\n{driver.page_source[:2000]}")

        # Log elements for each key selector before interaction
        for selector in ["#Username", "#nextBtn", "#i0118", "#idSIButton9"]:
            elems = driver.find_elements(By.CSS_SELECTOR, selector)
            logger.info(f"Found {len(elems)} elements for selector '{selector}' before interaction")
            for i, elem in enumerate(elems):
                try:
                    logger.info(f"Element {i}: tag={elem.tag_name}, id={elem.get_attribute('id')}, visible={elem.is_displayed()}")
                except Exception:
                    pass

        username_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#Username")))
        username_input.send_keys(user_email)
        next_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#nextBtn")))
        next_btn.click()

        logger.info(f"Current URL after username/next: {driver.current_url}")
        logger.debug(f"Page source after username/next:\n{driver.page_source[:2000]}")

        password_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#i0118")))
        password_input.send_keys(PASSWORD)
        submit_btn = wait.until(EC.element_to_be_clickable((By.ID, "idSIButton9")))
        submit_btn.click()

        logger.info(f"Current URL after password/submit: {driver.current_url}")
        logger.debug(f"Page source after password/submit:\n{driver.page_source[:2000]}")

        try:
            logger.info("start wait for post-login elements")
            time.sleep(1)
            # Log elements for each key selector before wait
            for selector in ["#passwordError, .error, .alert-error", "#idSIButton9", "#attendance"]:
                elems = driver.find_elements(By.CSS_SELECTOR, selector)
                logger.info(f"Found {len(elems)} elements for selector '{selector}' before wait")
                for i, elem in enumerate(elems):
                    try:
                        logger.info(f"Element {i}: tag={elem.tag_name}, id={elem.get_attribute('id')}, visible={elem.is_displayed()}")
                    except Exception:
                        pass

            # Wait for any of the elements to appear
            element = wait.until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#passwordError, .error, .alert-error")),
                    EC.presence_of_element_located((By.ID, "idSIButton9")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#attendance"))
                )
            )

            logger.info(f"Element found after wait: tag={element.tag_name}, id={element.get_attribute('id')}, visible={element.is_displayed()}")
            logger.info(f"Current URL after wait: {driver.current_url}")
            logger.debug(f"Page source after wait:\n{driver.page_source[:2000]}")

            # Check if password error is present and visible
            error_elem = None
            try:
                error_elem = driver.find_element(By.CSS_SELECTOR, "#passwordError, .error, .alert-error")
                if error_elem.is_displayed():
                    logger.error(f"Wrong WolfNet password detected for {user_email} (error element visible)")
                    screenshot_path = f"/tmp/wolfnet_debug_{user_email}_{int(time.time())}.png"
                    driver.save_screenshot(screenshot_path)
                    from forum.services.utils import upload_screenshot_to_storage
                    s3_url = upload_screenshot_to_storage(screenshot_path)
                    if s3_url:
                        logger.info(f"Debug screenshot available at: {s3_url}")
                    return {"success": False, "error": "Invalid WolfNet credentials", "error_type": "wrong_password"}
            except Exception as e:
                logger.debug(f"No error element found: {e}")

            # If attendance is present, login is successful
            if element.get_attribute("id") == "attendance" or "attendance" in element.get_attribute("id"):
                logger.info(f"Successfully logged in for {user_email}")
                time.sleep(1)
                return {"success": True}

            # If idSIButton9 is present and no error, proceed
            if element.get_attribute("id") == "idSIButton9":
                button = wait.until(EC.element_to_be_clickable((By.ID, "idSIButton9")))
                button.click()
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#attendance")))
                time.sleep(1)
                logger.info(f"Successfully logged in for {user_email} after handling stay signed in prompt")
                return {"success": True}

            # Fallback: treat as wrong password if error element is present
            logger.error(f"Wrong WolfNet password detected for {user_email} (fallback)")
            screenshot_path = f"/tmp/wolfnet_debug_{user_email}_{int(time.time())}.png"
            driver.save_screenshot(screenshot_path)
            from forum.services.utils import upload_screenshot_to_storage
            s3_url = upload_screenshot_to_storage(screenshot_path)
            if s3_url:
                logger.info(f"Debug screenshot available at: {s3_url}")
            return {"success": False, "error": "Invalid WolfNet credentials", "error_type": "wrong_password"}
        except Exception as e:
            import traceback
            logger.error(f"Exception during post-login wait: {e}")
            logger.error(traceback.format_exc())
            screenshot_path = f"/tmp/wolfnet_debug_{user_email}_{int(time.time())}.png"
            driver.save_screenshot(screenshot_path)
            from forum.services.utils import upload_screenshot_to_storage
            s3_url = upload_screenshot_to_storage(screenshot_path)
            if s3_url:
                logger.info(f"Debug screenshot available at: {s3_url}")
            # Log all elements for selectors again
            for selector in ["#passwordError, .error, .alert-error", "#idSIButton9", "#attendance"]:
                elems = driver.find_elements(By.CSS_SELECTOR, selector)
                logger.info(f"Found {len(elems)} elements for selector '{selector}' after exception")
                for i, elem in enumerate(elems):
                    try:
                        logger.info(f"Element {i}: tag={elem.tag_name}, id={elem.get_attribute('id')}, visible={elem.is_displayed()}")
                    except Exception:
                        pass
            logger.debug(f"Page source after exception:\n{driver.page_source[:2000]}")
            return {"success": False, "error": f"Login timeout or page loading issue: {str(e)}", "error_type": "timeout"}
                    
    except Exception as e:
        try:
            account_nav = driver.find_element(By.CSS_SELECTOR, "#account-nav")
            if account_nav:
                return {"success": True}
        except Exception as inner_e1:
            try:
                calender_subnav = driver.find_element(By.CSS_SELECTOR, "#calendar-subnav")
                if calender_subnav:
                    return {"success": True}
            except Exception as inner_e2:
                logger.info("Issue in finding navs", inner_e2)
                pass

        logger.error(f"Login timeout or page loading issue for {user_email}: {str(e)}")
        return {"success": False, "error": f"Login timeout or page loading issue: {str(e)}", "error_type": "timeout"}

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to login for {user_email}: {error_msg}")
        
        # Determine error type based on the exception
        if "element" in error_msg.lower() and ("username" in error_msg.lower() or "password" in error_msg.lower()):
            return {"success": False, "error": f"Login form elements not found: {error_msg}", "error_type": "page_structure"}
        elif "timeout" in error_msg.lower():
            return {"success": False, "error": f"Page timeout: {error_msg}", "error_type": "timeout"}
        elif "network" in error_msg.lower() or "connection" in error_msg.lower():
            return {"success": False, "error": f"Network error: {error_msg}", "error_type": "network"}
        else:
            return {"success": False, "error": f"General login error: {error_msg}", "error_type": "general"}

def check_user_grades_core(user_email):
    """
    Args:
        user_email (str): User's school email address
    
    Returns:
        dict: Result with success status and error message if failed
    """
    logger.info(f"Starting grade check for user: {user_email}")
    LOGIN_URL = "https://wpga.myschoolapp.com/"

    user_obj = User.objects.get(school_email=user_email)
    profile = getattr(user_obj, 'userprofile', None)
    wolfnet_password = None
    if profile:
        wolfnet_password = profile.wolfnet_password
    if not wolfnet_password:
        logger.warning(f"User {user_email} does not have a WolfNet password. Skipping grade check.")
        return {
            "success": False,
            "error": "No WolfNet password found. Please add your WolfNet password in your profile settings to enable grade checking."
        }

    # Use memory-optimized WebDriver
    driver, temp_user_data_dir = create_webdriver_with_cleanup()
    wait = WebDriverWait(driver, 6)  # Reduced timeout for memory efficiency

    try:
        login_result = login_to_wolfnet(user_email, driver, wait)
        if not login_result["success"]:
            if login_result["error_type"] == "wrong_password":
                return {"success": False, "error": "wrong_password"}
            elif login_result["error_type"] == "no_courses":
                return {"success": False, "error": f"{login_result['error']}", "error_type": "no_courses"}
            else:
                return {"success": False, "error": f"Failed to login to WolfNet: {login_result['error']}"}

        # Check if login was successful but with limited content (account-nav found but no course content)
        if login_result.get("message") and "account navigation found" in login_result["message"]:
            logger.info(f"Login successful for {user_email} but no course content available for grade checking")

        # Wait for courses to load
        try:
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".collapse")))
        except Exception as e:
            logger.info(f"No course content found for {user_email} - this is expected for grade checking when account-nav login fallback was used")
            return {"success": False, "error": "No course content available for grade checking", "error_type": "no_courses"}
            
        course_divs = driver.find_elements(By.CSS_SELECTOR, ".collapse")
        section_ids = []
        section_id_to_course_name = {}
        for div in course_divs:
            div_id = div.get_attribute("id")
            # Only process divs whose IDs match 'course' followed by digits (e.g., 'course114310942')
            if div_id and re.match(r"^course\d+$", div_id):
                sid = div_id.replace("course", "")
                section_ids.append(sid)
                try:
                    parent = div.find_element(By.XPATH, "..")
                    a_tag = parent.find_element(By.TAG_NAME, "a")
                    h3 = a_tag.find_element(By.TAG_NAME, "h3")
                    course_name = h3.text.strip()
                except Exception:
                    course_name = "Unknown Course"
                section_id_to_course_name[sid] = course_name

        # logger.info(f"Section IDs for {user_email}: {section_ids}")

        # Get studentId from #profile-link
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#profile-link")))
        profile_link = driver.find_element(By.CSS_SELECTOR, "#profile-link")
        href = profile_link.get_attribute("href")
        m = re.search(r"profile/(\d+)/contactcard", href)
        student_id = m.group(1) if m else None
        # logger.info(f"Student ID for {user_email}: {student_id}")

        # Get cookies from Selenium to use in requests
        selenium_cookies = driver.get_cookies()
        cookies = {c['name']: c['value'] for c in selenium_cookies}

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": "https://wpga.myschoolapp.com/",
        }

        # For each sectionId, get markingPeriodId and then hydrategradebook JSON
        user_obj = User.objects.get(school_email=user_email)

        # Get marking periods once (using the first section_id)
        marking_period_id = None
        if section_ids:
            first_section_id = section_ids[0]
            snapshot_qs = GradebookSnapshot.objects.filter(
                user=user_obj,
                section_id=first_section_id
            ).order_by('-timestamp')
            if snapshot_qs.exists():
                snapshot = snapshot_qs.first()
                mpid = getattr(snapshot, 'marking_period_id', None)
                if mpid:
                    marking_period_id = mpid
            # If not found, fetch from API
            if not marking_period_id:
                mp_url = f"https://wpga.myschoolapp.com/api/datadirect/GradeBookMarkingPeriodList?sectionId={first_section_id}"
                mp_resp = requests.get(mp_url, cookies=cookies, headers=headers, timeout=20)
                if mp_resp.status_code == 200:
                    mp_json = mp_resp.json()
                    if mp_json:
                        marking_period_id = mp_json[0].get("MarkingPeriodId")
        if not marking_period_id:
            logger.error(f"Could not fetch marking period id for {user_email}")
            return

        # Collect all email messages for all courses
        all_email_messages = []
        recipient = user_obj
        sender = user_obj
        notification_type = "grade_update"
        
        # Process sections asynchronously
        import asyncio
        import concurrent.futures
        
        def process_section(section_id):
            """Process a single section synchronously with timeout and better error handling"""
            section_messages = []
            
            try:
                hydrate_url = (
                    f"https://wpga.myschoolapp.com/api/gradebook/hydrategradebook?"
                    f"sectionId={section_id}&markingPeriodId={marking_period_id}"
                    f"&sortAssignmentId=null&sortSkillPk=null&sortDesc=null&sortCumulative=null"
                    f"&studentUserId={student_id}&fromProgress=true"
                )
                hydrate_resp = requests.get(hydrate_url, cookies=cookies, headers=headers, timeout=20)
                if hydrate_resp.status_code == 200:
                    hydrate_json = hydrate_resp.json()
                    assignments = []
                    roster = hydrate_json.get("Roster", [])
                    if roster:
                        for a in roster[0].get("AssignmentGrades", []):
                            assignments.append({
                                "assignment_id": a.get("AssignmentId"),
                                "name": a.get("AssignmentType", "").strip(),
                                "points_earned": a.get("PointsEarned"),
                                "max_points": a.get("MaxPoints"),
                                "comment": a.get("Comment", "").strip(),
                                "assignment_type": a.get("AssignmentType", "").strip(),
                                "assignment_type_id": a.get("AssignmentTypeId"),
                                "skills": [
                                    {
                                        "skill_id": s.get("SkillId"),
                                        "skill_name": s.get("SkillName"),
                                        "rating": s.get("Rating"),
                                        "rating_desc": s.get("RatingDesc")
                                    }
                                    for s in a.get("AssignmentSkillList", [])
                                ]
                            })
                        # Fetch AssignmentPerformanceStudent JSON for assignment names
                        aps_url = (
                            f"https://wpga.myschoolapp.com/api/gradebook/AssignmentPerformanceStudent?"
                            f"sectionId={section_id}&markingPeriodId={marking_period_id}&studentId={student_id}"
                        )
                        aps_resp = requests.get(aps_url, cookies=cookies, headers=headers, timeout=20)
                        assignment_names = {}
                        if aps_resp.status_code == 200:
                            aps_json = aps_resp.json()
                            for entry in aps_json:
                                aid = entry.get("AssignmentId")
                                short_desc = entry.get("AssignmentShortDescription")
                                if aid and short_desc:
                                    assignment_names[aid] = short_desc

                        # Compare with previous snapshot
                        snapshot_qs = GradebookSnapshot.objects.filter(
                            user=user_obj,
                            section_id=section_id,
                            marking_period_id=str(marking_period_id)
                        ).order_by('-timestamp')

                        if snapshot_qs.exists():
                            snapshot = snapshot_qs.first()
                            old_assignments = snapshot.json_data
                            changes = compare_assignments(old_assignments, assignments)
                            logger.info(f"Changes for {user_email} - section {section_id}, marking period {marking_period_id}: {len(changes)} changes found")

                            course_name = section_id_to_course_name.get(str(section_id), "Unknown Course")
                            for change in changes:
                                # logger.info(f"Processing change for {user_email}: {change}")
                                assignment = change["assignment"]
                                assignment_id = assignment.get("assignment_id")
                                assignment_name = strip_tags(assignment_names.get(assignment_id) or assignment.get("name") or assignment.get("assignment_type"))
                                skills = assignment.get("skills", [])
                                prof_skills = [s for s in skills if s.get("rating_desc", "")]
                                has_proficiency = bool(prof_skills)
                                if has_proficiency:
                                    prof_list = [f"<strong>{s.get('skill_name')}:</strong> {s.get('rating_desc')}" for s in prof_skills]
                                    grade_info = "<br>".join(prof_list)
                                else:
                                    points_earned = assignment.get("points_earned")
                                    max_points = assignment.get("max_points")
                                    if points_earned is not None and max_points:
                                        try:
                                            percent = round((points_earned / max_points) * 100, 2)
                                        except Exception:
                                            percent = None
                                        grade_info = f"<br><strong>Grade:</strong> {points_earned}/{max_points} ({percent}%)" if percent is not None else f"Grade: {points_earned}/{max_points}"
                                    else:
                                        grade_info = "Grade information not available."

                                # Create HTML message for email
                                html_message = f"<h3>{assignment_name} ({course_name}): </h3><br>"
                                if change["type"] == "new":
                                    html_message += f"New assignment graded.<br>{grade_info}<br>Comment: {assignment.get('comment')}"
                                elif change["type"] == "skill_changed":
                                    skill = change["skill"]
                                    html_message += f"Competency '<strong>{skill.get('skill_name')}</strong>' updated to '<strong>{skill.get('rating_desc')}</strong>'. {grade_info}"
                                elif change["type"] == "points_changed":
                                    html_message += f"Points changed to {assignment.get('points_earned')}/{assignment.get('max_points')}. {grade_info}"
                                elif change["type"] == "comment_changed":
                                    html_message += f"Comment updated.<br>{grade_info}<br>Comment: {assignment.get('comment')}"
                                else:
                                    html_message += f"Graded or updated.<br>{grade_info}"

                                # Create clean text message for notification/push notification
                                clean_grade_info = strip_tags(grade_info.replace("<br>", " "))
                                clean_message = f"{assignment_name} ({course_name}): "
                                if change["type"] == "new":
                                    clean_message += f"New assignment graded. {clean_grade_info}"
                                    if assignment.get('comment'):
                                        clean_message += f" Comment: {assignment.get('comment')}"
                                elif change["type"] == "skill_changed":
                                    skill = change["skill"]
                                    clean_message += f"Competency '{skill.get('skill_name')}' updated to '{skill.get('rating_desc')}'. {clean_grade_info}"
                                elif change["type"] == "points_changed":
                                    clean_message += f"Points changed to {assignment.get('points_earned')}/{assignment.get('max_points')}. {clean_grade_info}"
                                elif change["type"] == "comment_changed":
                                    clean_message += f"Comment updated. {clean_grade_info}"
                                    if assignment.get('comment'):
                                        clean_message += f" Comment: {assignment.get('comment')}"
                                else:
                                    clean_message += f"Graded or updated. {clean_grade_info}"

                                section_messages.append(html_message)

                                from forum.services.notification_services import send_notification_service
                                send_notification_service(
                                    recipient=recipient,
                                    sender=sender,
                                    notification_type=notification_type,
                                    message=clean_message,
                                )

                            snapshot.json_data = assignments
                            snapshot.timestamp = django.utils.timezone.now()
                            snapshot.save()
                            logger.info(f"Updated snapshot for {user_email} - section {section_id}, marking period {marking_period_id}")
                        else:
                            GradebookSnapshot.objects.create(
                                user=user_obj,
                                section_id=section_id,
                                marking_period_id=str(marking_period_id),
                                json_data=assignments
                            )
                            logger.info(f"Created new snapshot for {user_email} - section {section_id}, marking period {marking_period_id}")
                else:
                    logger.error(f"Failed to get hydrategradebook for {user_email} - section {section_id}, marking period {marking_period_id}")
                
            except requests.Timeout:
                logger.error(f"Timeout while processing section {section_id} for {user_email}")
            except Exception as e:
                logger.error(f"Error processing section {section_id} for {user_email}: {str(e)}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
            
            return section_messages
        
        # Process sections sequentially to reduce memory usage instead of concurrent.futures
        # Using ThreadPoolExecutor with max_workers=1 to maintain structure but reduce memory
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future_to_section = {executor.submit(process_section, section_id): section_id for section_id in section_ids}
            
            for future in concurrent.futures.as_completed(future_to_section):
                section_id = future_to_section[future]
                try:
                    section_messages = future.result()
                    if section_messages:
                        all_email_messages.extend(section_messages)
                except Exception as exc:
                    logger.error(f"Section {section_id} generated an exception: {exc}")
                    import traceback
                    logger.error(f"Full traceback for section {section_id}: {traceback.format_exc()}")

        if all_email_messages:
            email_subject = f"WolfKey Grade Update:"
            email_body = f"""
                <html>
                <body>
                    <h2>WolfKey Grade Updates</h2>
                    <p>Hello {recipient.get_full_name()},</p>
                    {''.join([f'<li>{msg}</li>' for msg in all_email_messages])}
                    <br>
                    <p>Best regards,<br>WolfKey Team</p>
                </body>
                </html>
            """
            logger.info(f"Sending combined grade update notification to {recipient.personal_email}: {all_email_messages}")
            send_email_notification.delay(
                recipient.personal_email,
                email_subject,
                email_body
            )
    finally:
        try:
            driver.quit()
        except Exception as e:
            logger.warning(f"Error quitting driver: {e}")
        # Remove temporary user-data-dir if created
        try:
            if temp_user_data_dir:
                shutil.rmtree(temp_user_data_dir, ignore_errors=True)
                logger.info(f"Removed temp user-data-dir: {temp_user_data_dir}")
        except Exception as e:
            logger.warning(f"Error removing temp user-data-dir {temp_user_data_dir}: {e}")

        # Wait a moment for driver to fully close
        time.sleep(0.5)
    # Force garbage collection to free memory
    gc.collect()
    logger.info(f"Grade check completed and cleaned up for {user_email}")

@shared_task(bind=True, queue='grades', routing_key='grades.single_user')
def check_single_user_grades(self, user_email):
    """
    Args:
        user_email (str): User's school email address
    
    Returns:
        dict: Result from check_user_grades_core function
    """
    try:
        return check_user_grades_core(user_email)
    except Exception as e:
        logger.error(f"Error checking grades for {user_email}: {str(e)}")
        raise

@shared_task(bind=True, queue='grades', routing_key='grades.coordination')
def check_all_user_grades_sequential_dispatch(self):
    """
    Dispatch individual grade check tasks for all users without waiting
    
    Args:
        None
    
    Returns:
        dict: Summary with dispatched task information
    """
    users = list(User.objects.filter(school_email__isnull=False).exclude(school_email=''))
    logger.info(f"Starting sequential dispatch of grade checks for {len(users)} users")
    
    results = []
    successful_dispatches = 0
    failed_dispatches = 0
    
    for idx, user in enumerate(users, 1):
        logger.info(f"Dispatching task for user {idx}/{len(users)}: {user.school_email}")
        
        try:
            # Dispatch task without waiting for completion
            task = check_single_user_grades.delay(user.school_email)
            logger.info(f"Dispatched task {task.id} for {user.school_email}")
            
            results.append({
                "user": user.school_email,
                "status": "dispatched",
                "task_id": task.id
            })
            successful_dispatches += 1
            
        except Exception as e:
            logger.error(f"Failed to dispatch task for {user.school_email}: {str(e)}")
            results.append({
                "user": user.school_email,
                "status": "failed_to_dispatch",
                "error": str(e),
                "task_id": None
            })
            failed_dispatches += 1
    
    summary = {
        "total_users": len(users),
        "successful_dispatches": successful_dispatches,
        "failed_dispatches": failed_dispatches,
        "results": results,
        "message": f"Dispatched tasks for {len(users)} users: {successful_dispatches} successful, {failed_dispatches} failed"
    }
    
    logger.info(f"Sequential dispatch completed: {summary['message']}")
    return summary

@shared_task(bind=True, queue='grades', routing_key='grades.coordination')  
def check_user_grades_batched_dispatch(self, batch_size=1):
    """
    Dispatch users in small batches without waiting for completion
    
    Args:
        batch_size (int): Number of users to process simultaneously per batch (default 1 for memory efficiency)
    
    Returns:
        dict: Summary with dispatched batches and results
    """
    users = list(User.objects.filter(school_email__isnull=False).exclude(school_email=''))
    logger.info(f"Starting batched dispatch of grade checks for {len(users)} users (batch size: {batch_size})")
    
    # Split users into batches
    batches = [users[i:i + batch_size] for i in range(0, len(users), batch_size)]
    
    all_results = []
    total_successful_dispatches = 0
    total_failed_dispatches = 0
    
    for batch_idx, batch in enumerate(batches, 1):
        logger.info(f"Dispatching batch {batch_idx}/{len(batches)} ({len(batch)} users)")
        
        # Dispatch all tasks in this batch without waiting
        for user in batch:
            try:
                task = check_single_user_grades.delay(user.school_email)
                logger.info(f"Dispatched task {task.id} for {user.school_email}")
                
                all_results.append({
                    "user": user.school_email,
                    "status": "dispatched",
                    "task_id": task.id
                })
                total_successful_dispatches += 1
                
            except Exception as e:
                logger.error(f"Failed to dispatch task for {user.school_email}: {str(e)}")
                all_results.append({
                    "user": user.school_email,
                    "status": "failed_to_dispatch",
                    "error": str(e),
                    "task_id": None
                })
                total_failed_dispatches += 1
        
        logger.info(f"Dispatched batch {batch_idx}/{len(batches)}")
    
    summary = {
        "total_users": len(users),
        "total_batches": len(batches),
        "batch_size": batch_size,
        "successful_dispatches": total_successful_dispatches,
        "failed_dispatches": total_failed_dispatches,
        "results": all_results,
        "message": f"Dispatched {len(users)} users in {len(batches)} batches: {total_successful_dispatches} successful, {total_failed_dispatches} failed"
    }
    
    logger.info(f"Batched dispatch completed: {summary['message']}")
    return summary

@shared_task(bind=True, queue='grades', routing_key='grades.trigger')
def periodic_grade_check_trigger(self):
    """
    Trigger periodic grade checking with sequential dispatch

    Args:
        None

    Returns:
        None
    """
    logger.info("Starting periodic grade check trigger - using sequential dispatch")
    check_all_user_grades_sequential_dispatch.delay()
    logger.info("Dispatched sequential grade check task")

@shared_task(bind=True, queue='general', routing_key='general.email')
def send_email_notification(self, recipient_email, subject, message):
    """
    Args:
        recipient_email (str): Email address to send to
        subject (str): Email subject line
        message (str): HTML email content
    
    Returns:
        str: Success message or raises exception on failure
    """
    from django.core.mail import send_mail
    from django.conf import settings
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email],
            fail_silently=False,
            html_message=message
        )
        logger.info(f"Email sent successfully to {recipient_email}")
        return f"Email sent to {recipient_email}"
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
        raise

@shared_task(bind=True, queue='general', routing_key='general.auto')
def auto_complete_courses(self, user_email, password=None):
    """
    Args:
        user_email (str): User's school email address
        password (str, optional): WolfNet password, uses stored password if None
    
    Returns:
        dict: Result with success status, courses data, and raw_data if successful, or error message if failed
    """
    # TEMPORARILY DISABLED - WolfNet integration issues being resolved with IT department
    logger.info(f"Auto-complete courses blocked for user: {user_email} - WolfNet integration temporarily disabled")
    return {
        "success": False,
        "error": "WolfNet auto-complete is temporarily unavailable while we sort out issues with the IT department. Please check back later.",
        "error_type": "temporarily_disabled"
    }
    
    # ORIGINAL CODE - COMMENTED OUT TEMPORARILY
    """
    logger.info(f"Starting auto-complete courses for user: {user_email}")
    
    # Use memory-optimized WebDriver
    driver, temp_user_data_dir = create_webdriver_with_cleanup()
    wait = WebDriverWait(driver, 6)  # Reduced timeout

    try:
        login_result = login_to_wolfnet(user_email, driver, wait, password)
        if not login_result["success"]:
            if login_result["error_type"] == "wrong_password":
                return {"success": False, "error": "wrong_password", "error_type": "authentication"}
            elif login_result["error_type"] == "no_courses":
                return {"success": False, "error": f"{login_result['error']}", "error_type": "no_courses"}
            else:
                return {"success": False, "error": f"Failed to login to WolfNet: {login_result['error']}", "error_type": "authentication"}

        # Check if login was successful but with limited content (account-nav found but no course content)
        if login_result.get("message") and "account navigation found" in login_result["message"]:
            logger.info(f"Login successful for {user_email} but no course content available for auto-completion")

        # Wait for the page to load and find the first .subnav-multicol element
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".subnav-multicol")))
            subnav_elements = driver.find_elements(By.CSS_SELECTOR, ".subnav-multicol")
            
            if not subnav_elements:
                logger.error(f"No .subnav-multicol elements found for {user_email}")
                return {"success": False, "error": "Course navigation not found on page", "error_type": "page_loading"}
        except Exception as e:
            # This is expected when account-nav login fallback was used
            if login_result.get("message") and "account navigation found" in login_result["message"]:
                logger.info(f"No course navigation found for {user_email} - expected with account-nav login fallback")
                return {"success": False, "error": "No course content available for auto-completion", "error_type": "no_courses"}
            logger.error(f"Failed to load course navigation elements for {user_email}: {str(e)}")
            return {"success": False, "error": "Course navigation failed to load", "error_type": "page_loading"}
        
        # Take the first .subnav-multicol element
        subnav = subnav_elements[0]
        
        # Find all span.multi.title elements in the subnav
        try:
            title_spans = subnav.find_elements(By.CSS_SELECTOR, "span.multi.title")
            
            if not title_spans:
                logger.warning(f"No course title spans found for {user_email}")
                return {"success": False, "error": "No course titles found in navigation", "error_type": "page_structure"}
        except Exception as e:
            logger.error(f"Failed to find course title elements for {user_email}: {str(e)}")
            return {"success": False, "error": "Failed to parse course navigation structure", "error_type": "page_structure"}

        courses_data = {}
        for title_span in title_spans:
            try:
                # Try multiple ways to get the text
                text_direct = title_span.text.strip()
                text_inner = title_span.get_attribute('innerText').strip() if title_span.get_attribute('innerText') else ''
                text_content = title_span.get_attribute('textContent').strip() if title_span.get_attribute('textContent') else ''

                # Use the first non-empty value
                course_text = text_direct or text_inner or text_content

                # Only process if it matches the block course pattern
                if " (" in course_text and course_text.endswith(")"):
                    block_match = re.search(r'\(([^)]+)\)$', course_text)
                    if block_match:
                        block = block_match.group(1)
                        course_name_part = course_text.split(" (", 1)[0]
                        if " - " in course_name_part:
                            course_name = course_name_part.split(" - ", 1)[0].strip()
                        else:
                            course_name = course_name_part.strip()
                        if re.match(r'^[12][A-E]|Flex\d*$', block):
                            if block.startswith("Flex"):
                                continue  # Skip flex blocks
                            courses_data[block] = {
                                "name": course_name,
                                "block": block,
                                "raw_text": course_text
                            }
            except Exception as e:
                logger.warning(f"Error parsing span.multi.title for {user_email}: {str(e)}")
                continue
        logger.info(f"Found {len(courses_data)} courses for {user_email}: {courses_data}")
        
        if not courses_data:
            logger.warning(f"No valid courses found for {user_email}")
            return {"success": False, "error": "No valid courses found in schedule", "error_type": "no_courses"}

        matched_courses = {}
        logger.info(courses_data)
        
        for block, course_info in courses_data.items():
            course_name = course_info["name"]

            
            # Create a mock request object for course_search
            mock_request = type('MockRequest', (), {
                'GET': {'q': course_name},
                'method': 'GET'
            })()
            
            try:
                from forum.services.course_services import course_search
                
                search_response = course_search(mock_request)
                search_data = search_response.content.decode('utf-8')
                import json
                courses = json.loads(search_data)
                
                if courses:
                    best_match = courses[0]
                    matched_courses[block] = {
                        "id": best_match["id"],
                        "name": best_match["name"],
                        "category": best_match["category"],
                        "experienced_count": best_match["experienced_count"]
                    }
                    logger.info(f"Matched {course_name} to {best_match['name']} for block {block}")
                else:
                    logger.warning(f"No match found for course: {course_name} in block {block}")
                    
            except Exception as e:
                logger.error(f"Error searching for course {course_name}: {str(e)}")
                continue
        
        # Try to get the user and use BlockSerializer format
        try:
            from django.contrib.auth import get_user_model
            from forum.serializers import BlockSerializer
            User = get_user_model()
            
            user = User.objects.get(school_email=user_email)
            if hasattr(user, 'userprofile'):
                # User exists and has profile - use BlockSerializer
                serializer = BlockSerializer(user.userprofile)
                return {
                    "success": True,
                    "user_data": serializer.data,
                }
        except User.DoesNotExist:
            pass
        except Exception as e:
            logger.warning(f"Could not use BlockSerializer for {user_email}: {str(e)}")
        
        # User doesn't exist or no profile - create compatible format manually
        schedule = {}
        all_blocks = ['1A', '1B', '1D', '1E', '2A', '2B', '2C', '2D', '2E']
        for block in all_blocks:
            if block in matched_courses:
                schedule[block] = {
                    'course': matched_courses[block]['name'],
                    'course_id': matched_courses[block]['id']
                }
            else:
                schedule[block] = {
                    'course': None,
                    'course_id': None
                }
        
        # Create BlockSerializer-compatible format for registration
        user_data = {
            'user_id': None,  # No user yet during registration
            'username': None,
            'full_name': None,
            'profile_picture_url': None,
            'schedule': schedule,
            'grade_level': None
        }
        
        return {
            "success": True,
            "user_data": user_data,
        }
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error in auto_complete_courses for {user_email}: {error_message}")
        
        if "login" in error_message.lower() or "password" in error_message.lower():
            error_type = "authentication"
        elif "element" in error_message.lower() or "timeout" in error_message.lower() or "not found" in error_message.lower():
            error_type = "page_loading"
        else:
            error_type = "general"
            
        return {
            "success": False, 
            "error": error_message,
            "error_type": error_type
        }
    finally:
        try:
            driver.quit()
        except Exception as e:
            logger.warning(f"Error quitting driver: {e}")
        # Remove temporary user-data-dir if created
        try:
            if temp_user_data_dir:
                shutil.rmtree(temp_user_data_dir, ignore_errors=True)
                logger.info(f"Removed temp user-data-dir: {temp_user_data_dir}")
        except Exception as e:
            logger.warning(f"Error removing temp user-data-dir {temp_user_data_dir}: {e}")

        # Wait a moment for driver to fully close
        time.sleep(0.5)
        
        # Force garbage collection to free memory
        gc.collect()
        logger.info(f"Auto-complete courses completed and cleaned up for {user_email}")
    """


@shared_task(bind=True, queue='grades', routing_key='grades.wolfnet')
def check_wolfnet_password(self, user_email, password):
    """
    Check if WolfNet password is valid for a user
    
    Args:
        user_email (str): User's school email address
        password (str): WolfNet password to verify
    
    Returns:
        dict: Result with success status and error message if failed
    """
    # TEMPORARILY DISABLED - WolfNet integration issues being resolved with IT department
    logger.info(f"WolfNet password check blocked for user: {user_email} - WolfNet integration temporarily disabled")
    return {
        "success": False,
        "error": "WolfNet password verification is temporarily unavailable while we sort out issues with the IT department. Please check back later.",
        "error_type": "temporarily_disabled"
    }
    
    # ORIGINAL CODE - COMMENTED OUT TEMPORARILY
    # logger.info(f"Starting WolfNet password check for user: {user_email}")
    # 
    # # Use memory-optimized WebDriver
    # driver, temp_user_data_dir = create_webdriver_with_cleanup()
    # wait = WebDriverWait(driver, 6)
    #
    # try:
    #     login_result = login_to_wolfnet(user_email, driver, wait, password)
    #     logger.info(f"WolfNet password check completed for {user_email}: {login_result}")
    #     return login_result
    # 
    # except Exception as e:
    #     error_message = str(e)
    #     logger.error(f"Error checking WolfNet password for {user_email}: {error_message}")
    #     
    #     if "login" in error_message.lower() or "password" in error_message.lower():
    #         error_type = "authentication"
    #     elif "element" in error_message.lower() or "timeout" in error_message.lower():
    #         error_type = "page_loading"
    #     else:
    #         error_type = "general"
    #         
    #     return {
    #         "success": False, 
    #         "error": error_message,
    #         "error_type": error_type
    #     }
    # finally:
    #     try:
    #         driver.quit()
    #     except Exception as e:
    #         logger.warning(f"Error quitting driver: {e}")
    #     # Remove temporary user-data-dir if created
    #     try:
    #         if temp_user_data_dir:
    #             shutil.rmtree(temp_user_data_dir, ignore_errors=True)
    #             logger.info(f"Removed temp user-data-dir: {temp_user_data_dir}")
    #     except Exception as e:
    #         logger.warning(f"Error removing temp user-data-dir {temp_user_data_dir}: {e}")
    #
    #     # Wait a moment for driver to fully close
    #     time.sleep(0.5)
    #     
    #     # Force garbage collection
    #     gc.collect()
    #     logger.info(f"Cleaned up WebDriver session for {user_email}")