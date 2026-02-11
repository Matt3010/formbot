"""Tests for app.services.task_executor.TaskExecutor."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from tests.conftest import (
    make_task,
    make_form_definition,
    make_form_field,
    _make_mock_page,
    _make_mock_context,
    _make_mock_browser,
    _make_mock_playwright,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_db_for_task(mock_db, task, form_defs, fields_by_form_def_id):
    """Wire up mock_db.query(...).filter(...).first()/.all() chains.

    ``fields_by_form_def_id`` maps form_def.id -> list of FormField mocks.
    """

    def _query_side_effect(model):
        q = MagicMock()

        model_name = getattr(model, "__name__", "") or str(model)

        if model_name == "Task":
            q.filter.return_value.first.return_value = task
            return q
        elif model_name == "FormDefinition":
            q.filter.return_value.order_by.return_value.all.return_value = form_defs
            return q
        elif model_name == "FormField":
            # Called once per form_def during field filling
            def _filter_side_effect(*args, **kwargs):
                inner = MagicMock()
                # We need to figure out which form_def_id was requested.
                # The executor calls FormField.form_definition_id == form_def.id
                # We'll match based on call order.
                return inner

            # Simpler approach: return fields in sequence via side_effect
            q.filter.return_value.order_by.return_value.all = MagicMock(
                side_effect=[
                    fields_by_form_def_id.get(fd.id, []) for fd in form_defs
                ]
            )
            return q

        return q

    mock_db.query = MagicMock(side_effect=_query_side_effect)


def _build_executor_patches(page, browser):
    """Return patches for async_playwright and apply_stealth."""
    context = _make_mock_context(page)
    browser_mock = browser
    browser_mock.new_context = AsyncMock(return_value=context)
    pw_cm = _make_mock_playwright(browser_mock)

    pw_patch = patch(
        "app.services.task_executor.async_playwright",
        return_value=pw_cm,
    )
    stealth_patch = patch(
        "app.services.task_executor.apply_stealth",
        AsyncMock(),
    )
    return pw_patch, stealth_patch, context


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_simple_single_form(mock_db, mock_vnc_manager):
    """Successful execution of a single login form with two text fields."""
    task_id = uuid.uuid4()
    form_def_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=form_def_id, task_id=task_id, step_order=1,
        page_url="https://example.com/login",
        form_selector="#login-form", submit_selector="#submit-btn",
        captcha_detected=False, two_factor_expected=False,
    )
    username_field = make_form_field(
        form_definition_id=form_def_id, field_name="username",
        field_type="text", field_selector="#username",
        preset_value="testuser", is_sensitive=False, is_file_upload=False,
        sort_order=0,
    )
    password_field = make_form_field(
        form_definition_id=form_def_id, field_name="password",
        field_type="password", field_selector="#password",
        preset_value="secret", is_sensitive=False, is_file_upload=False,
        sort_order=1,
    )

    _setup_db_for_task(mock_db, task, [form_def], {
        form_def_id: [username_field, password_field],
    })

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"
    assert "execution_id" in result
    assert "screenshot" in result

    # Verify navigation
    page.goto.assert_awaited_once()
    assert page.goto.call_args[0][0] == "https://example.com/login"

    # Verify form selector was waited for
    page.wait_for_selector.assert_awaited_once_with("#login-form", timeout=10000)

    # Verify fields were filled
    assert page.fill.await_count == 2
    fill_calls = page.fill.call_args_list
    assert fill_calls[0][0] == ("#username", "testuser")
    assert fill_calls[1][0] == ("#password", "secret")

    # Verify submit was clicked
    page.click.assert_awaited_once_with("#submit-btn")

    # Verify screenshot taken
    page.screenshot.assert_awaited_once()

    # Verify browser closed
    browser.close.assert_awaited_once()

    # Verify DB commit was called (execution log updates)
    assert mock_db.commit.call_count >= 2


@pytest.mark.asyncio
async def test_execute_multi_step(mock_db, mock_vnc_manager):
    """Execution with two form steps: login -> target form."""
    task_id = uuid.uuid4()
    fd1_id = uuid.uuid4()
    fd2_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def_1 = make_form_definition(
        id=fd1_id, task_id=task_id, step_order=1,
        page_url="https://example.com/login",
        form_selector="#login-form", submit_selector="#login-submit",
        captcha_detected=False, two_factor_expected=False,
    )
    form_def_2 = make_form_definition(
        id=fd2_id, task_id=task_id, step_order=2,
        page_url="https://example.com/dashboard/form",
        form_selector="#data-form", submit_selector="#data-submit",
        captcha_detected=False, two_factor_expected=False,
    )
    login_field = make_form_field(
        form_definition_id=fd1_id, field_name="user",
        field_type="text", field_selector="#user",
        preset_value="admin", sort_order=0,
    )
    data_field = make_form_field(
        form_definition_id=fd2_id, field_name="amount",
        field_type="number", field_selector="#amount",
        preset_value="100", sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def_1, form_def_2], {
        fd1_id: [login_field],
        fd2_id: [data_field],
    })

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"

    # Two navigations (one per step)
    assert page.goto.await_count == 2
    urls_navigated = [c[0][0] for c in page.goto.call_args_list]
    assert urls_navigated[0] == "https://example.com/login"
    assert urls_navigated[1] == "https://example.com/dashboard/form"

    # Two submits
    assert page.click.await_count == 2
    submit_selectors = [c[0][0] for c in page.click.call_args_list]
    assert "#login-submit" in submit_selectors
    assert "#data-submit" in submit_selectors

    # Two form selectors waited for
    assert page.wait_for_selector.await_count == 2


@pytest.mark.asyncio
async def test_execute_dry_run(mock_db, mock_vnc_manager):
    """Dry run stops before final submit and returns dry_run_ok."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/form",
        form_selector="#form", submit_selector="#submit",
        captcha_detected=False, two_factor_expected=False,
    )
    field = make_form_field(
        form_definition_id=fd_id, field_name="name",
        field_type="text", field_selector="#name",
        preset_value="John", sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [field]})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id), is_dry_run=True)

    assert result["status"] == "dry_run_ok"
    assert "screenshot" in result

    # Field was filled
    page.fill.assert_awaited_once_with("#name", "John")

    # Submit was NOT clicked (dry run)
    page.click.assert_not_awaited()

    # Screenshot was taken
    page.screenshot.assert_awaited_once()
    screenshot_kwargs = page.screenshot.call_args[1]
    assert screenshot_kwargs["full_page"] is True

    # Browser was closed
    browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_captcha_triggers_vnc_pause(mock_db, mock_vnc_manager):
    """When captcha_detected=True, a VNC pause is triggered before field filling."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/captcha",
        form_selector="#captcha-form", submit_selector="#submit",
        captcha_detected=True, two_factor_expected=False,
    )
    field = make_form_field(
        form_definition_id=fd_id, field_name="name",
        field_type="text", field_selector="#name",
        preset_value="Test", sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [field]})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, context = _build_executor_patches(page, browser)

    # VNC resumes successfully
    mock_vnc_manager.wait_for_resume = AsyncMock(return_value=True)

    with pw_patch, stealth_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"

    # VNC session was started
    mock_vnc_manager.start_session.assert_awaited_once()

    # VNC was waited on
    mock_vnc_manager.wait_for_resume.assert_awaited_once()

    # VNC was stopped after resume
    mock_vnc_manager.stop_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_2fa_triggers_post_submit_vnc(mock_db, mock_vnc_manager):
    """When two_factor_expected=True, VNC pause happens AFTER form submission."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/login",
        form_selector="#login-form", submit_selector="#submit",
        captcha_detected=False, two_factor_expected=True,
    )
    field = make_form_field(
        form_definition_id=fd_id, field_name="user",
        field_type="text", field_selector="#user",
        preset_value="admin", sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [field]})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, context = _build_executor_patches(page, browser)

    mock_vnc_manager.wait_for_resume = AsyncMock(return_value=True)

    with pw_patch, stealth_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"

    # Submit was clicked (2FA pause is POST-submit)
    page.click.assert_awaited_once_with("#submit")

    # VNC session was started for 2FA
    mock_vnc_manager.start_session.assert_awaited_once()
    mock_vnc_manager.wait_for_resume.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_vnc_timeout_fails(mock_db, mock_vnc_manager):
    """When VNC wait_for_resume times out, execution fails."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/captcha",
        form_selector="#form", submit_selector="#submit",
        captcha_detected=True, two_factor_expected=False,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: []})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, context = _build_executor_patches(page, browser)

    # VNC times out
    mock_vnc_manager.wait_for_resume = AsyncMock(return_value=False)

    with pw_patch, stealth_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "failed"
    assert "VNC timeout" in result["error"]


@pytest.mark.asyncio
async def test_execute_task_not_found(mock_db, mock_vnc_manager):
    """execute raises ValueError when the task does not exist."""
    mock_db.query.return_value.filter.return_value.first.return_value = None

    from app.services.task_executor import TaskExecutor

    executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)

    with pytest.raises(ValueError, match="not found"):
        await executor.execute("nonexistent-task-id")


@pytest.mark.asyncio
async def test_execute_form_selector_not_found(mock_db, mock_vnc_manager):
    """When the form selector is not found on the page, execution fails."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/form",
        form_selector="#nonexistent-form", submit_selector="#submit",
        captcha_detected=False, two_factor_expected=False,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: []})

    page = _make_mock_page()
    page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout 10000ms exceeded"))
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "failed"
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_execute_stealth_mode(mock_db, mock_vnc_manager):
    """Stealth is applied when stealth_enabled=True."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/form",
        form_selector="#form", submit_selector="#submit",
        captcha_detected=False, two_factor_expected=False,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: []})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    stealth_mock = AsyncMock()
    context = _make_mock_context(page)
    browser.new_context = AsyncMock(return_value=context)
    pw_cm = _make_mock_playwright(browser)

    pw_patch = patch(
        "app.services.task_executor.async_playwright",
        return_value=pw_cm,
    )
    stealth_patch = patch(
        "app.services.task_executor.apply_stealth",
        stealth_mock,
    )

    with pw_patch, stealth_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        await executor.execute(str(task_id), stealth_enabled=True)

    stealth_mock.assert_awaited_once_with(context)


@pytest.mark.asyncio
async def test_execute_stealth_disabled(mock_db, mock_vnc_manager):
    """Stealth is NOT applied when stealth_enabled=False."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/form",
        form_selector="#form", submit_selector="#submit",
        captcha_detected=False, two_factor_expected=False,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: []})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    stealth_mock = AsyncMock()
    context = _make_mock_context(page)
    browser.new_context = AsyncMock(return_value=context)
    pw_cm = _make_mock_playwright(browser)

    pw_patch = patch(
        "app.services.task_executor.async_playwright",
        return_value=pw_cm,
    )
    stealth_patch = patch(
        "app.services.task_executor.apply_stealth",
        stealth_mock,
    )

    with pw_patch, stealth_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        await executor.execute(str(task_id), stealth_enabled=False)

    stealth_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_field_filling_select(mock_db, mock_vnc_manager):
    """Select fields use page.select_option."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        form_selector="#form", submit_selector="#submit",
        captcha_detected=False, two_factor_expected=False,
    )
    select_field = make_form_field(
        form_definition_id=fd_id, field_name="country",
        field_type="select", field_selector="#country",
        preset_value="US", sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [select_field]})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"
    page.select_option.assert_awaited_once_with("#country", "US")


@pytest.mark.asyncio
async def test_execute_field_filling_checkbox(mock_db, mock_vnc_manager):
    """Checkbox fields use page.check / page.uncheck based on value."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        form_selector="#form", submit_selector="#submit",
        captcha_detected=False, two_factor_expected=False,
    )
    checkbox_on = make_form_field(
        form_definition_id=fd_id, field_name="agree",
        field_type="checkbox", field_selector="#agree",
        preset_value="true", sort_order=0,
    )
    checkbox_off = make_form_field(
        form_definition_id=fd_id, field_name="newsletter",
        field_type="checkbox", field_selector="#newsletter",
        preset_value="false", sort_order=1,
    )

    _setup_db_for_task(mock_db, task, [form_def], {
        fd_id: [checkbox_on, checkbox_off],
    })

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"
    page.check.assert_awaited_once_with("#agree")
    page.uncheck.assert_awaited_once_with("#newsletter")


@pytest.mark.asyncio
async def test_execute_field_filling_file_upload(mock_db, mock_vnc_manager):
    """File upload fields use page.set_input_files."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        form_selector="#form", submit_selector="#submit",
        captcha_detected=False, two_factor_expected=False,
    )
    file_field = make_form_field(
        form_definition_id=fd_id, field_name="document",
        field_type="file", field_selector="#document",
        preset_value="report.pdf", is_file_upload=True, sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [file_field]})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"
    page.set_input_files.assert_awaited_once()
    call_args = page.set_input_files.call_args[0]
    assert call_args[0] == "#document"
    assert "report.pdf" in call_args[1]


@pytest.mark.asyncio
async def test_execute_field_filling_hidden(mock_db, mock_vnc_manager):
    """Hidden fields use page.eval_on_selector to set value."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        form_selector="#form", submit_selector="#submit",
        captcha_detected=False, two_factor_expected=False,
    )
    hidden_field = make_form_field(
        form_definition_id=fd_id, field_name="token",
        field_type="hidden", field_selector="#token",
        preset_value="abc123", sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [hidden_field]})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"
    page.eval_on_selector.assert_awaited_once()
    call_args = page.eval_on_selector.call_args[0]
    assert call_args[0] == "#token"
    assert call_args[2] == "abc123"


@pytest.mark.asyncio
async def test_execute_skips_field_with_no_preset(mock_db, mock_vnc_manager):
    """Fields with preset_value=None are skipped during filling."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        form_selector="#form", submit_selector="#submit",
        captcha_detected=False, two_factor_expected=False,
    )
    no_value_field = make_form_field(
        form_definition_id=fd_id, field_name="optional",
        field_type="text", field_selector="#optional",
        preset_value=None, sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [no_value_field]})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"
    # No fill/select/check methods should have been called
    page.fill.assert_not_awaited()
    page.select_option.assert_not_awaited()
    page.check.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_field_error_continues(mock_db, mock_vnc_manager):
    """If a field fill fails, the error is logged but execution continues."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        form_selector="#form", submit_selector="#submit",
        captcha_detected=False, two_factor_expected=False,
    )
    bad_field = make_form_field(
        form_definition_id=fd_id, field_name="broken",
        field_type="text", field_selector="#broken",
        preset_value="value", sort_order=0,
    )
    good_field = make_form_field(
        form_definition_id=fd_id, field_name="working",
        field_type="text", field_selector="#working",
        preset_value="ok", sort_order=1,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [bad_field, good_field]})

    page = _make_mock_page()
    # First fill call fails, second succeeds
    page.fill = AsyncMock(side_effect=[Exception("Element not found"), None])
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    # Execution still succeeds (field errors are non-fatal)
    assert result["status"] == "success"
    # Both fills were attempted
    assert page.fill.await_count == 2


@pytest.mark.asyncio
async def test_execute_dry_run_multi_step(mock_db, mock_vnc_manager):
    """In a multi-step dry run, only the LAST step skips submit."""
    task_id = uuid.uuid4()
    fd1_id = uuid.uuid4()
    fd2_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def_1 = make_form_definition(
        id=fd1_id, task_id=task_id, step_order=1,
        page_url="https://example.com/login",
        form_selector="#login", submit_selector="#login-btn",
        captcha_detected=False, two_factor_expected=False,
    )
    form_def_2 = make_form_definition(
        id=fd2_id, task_id=task_id, step_order=2,
        page_url="https://example.com/form",
        form_selector="#form", submit_selector="#submit-btn",
        captcha_detected=False, two_factor_expected=False,
    )

    _setup_db_for_task(mock_db, task, [form_def_1, form_def_2], {
        fd1_id: [],
        fd2_id: [],
    })

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id), is_dry_run=True)

    assert result["status"] == "dry_run_ok"

    # First step's submit WAS clicked (dry run only skips the last step)
    page.click.assert_awaited_once_with("#login-btn")

    # Screenshot was taken
    page.screenshot.assert_awaited_once()
