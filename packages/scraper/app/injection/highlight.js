/**
 * FormBot Field Highlighter — injected into the target page.
 *
 * Namespace: window.__FORMBOT_HIGHLIGHT
 *
 * Provides visual overlays on form fields detected by Ollama,
 * and interactive modes for selecting/adding/removing fields.
 */
(function () {
  'use strict';

  if (window.__FORMBOT_HIGHLIGHT) return; // prevent double-injection

  const NS = '__FORMBOT_HIGHLIGHT';
  const Z = 2147483647;

  // Color palette by field type
  const TYPE_COLORS = {
    text: '#2196F3',       // blue
    password: '#2196F3',
    email: '#2196F3',
    tel: '#2196F3',
    url: '#2196F3',
    number: '#2196F3',
    search: '#2196F3',
    select: '#4CAF50',     // green
    checkbox: '#FF9800',   // orange
    radio: '#FF9800',
    file: '#9C27B0',       // purple
    submit: '#F44336',     // red
    button: '#F44336',
    hidden: '#607D8B',     // grey
    textarea: '#2196F3',
  };

  const DEFAULT_COLOR = '#2196F3';

  let _fields = [];
  let _overlays = [];
  let _inputListeners = []; // {el, handler} pairs for cleanup
  let _mode = 'select'; // select | add | remove
  let _focusedIndex = -1;

  function getColor(fieldType) {
    return TYPE_COLORS[(fieldType || '').toLowerCase()] || DEFAULT_COLOR;
  }

  function getElement(selector) {
    try {
      return document.querySelector(selector);
    } catch (e) {
      return null;
    }
  }

  function removeInputListeners() {
    _inputListeners.forEach(function (entry) {
      entry.el.removeEventListener('input', entry.handler);
    });
    _inputListeners = [];
  }

  function attachInputListeners() {
    removeInputListeners();

    _fields.forEach(function (field, index) {
      var el = getElement(field.field_selector);
      if (!el) return;

      var handler = function () {
        if (window.__formbot_onFieldValueChanged) {
          window.__formbot_onFieldValueChanged(JSON.stringify({
            index: index,
            selector: field.field_selector,
            value: el.value,
          }));
        }
      };

      el.addEventListener('input', handler);
      _inputListeners.push({ el: el, handler: handler });
    });
  }

  function removeOverlays() {
    _overlays.forEach(function (o) {
      if (o.outline) o.outline.remove();
      if (o.badge) o.badge.remove();
      if (o.label) o.label.remove();
    });
    _overlays = [];
  }

  function createOverlays() {
    removeOverlays();

    _fields.forEach(function (field, index) {
      var el = getElement(field.field_selector);
      if (!el) return;

      var rect = el.getBoundingClientRect();
      var scrollX = window.scrollX || window.pageXOffset;
      var scrollY = window.scrollY || window.pageYOffset;
      var color = getColor(field.field_type);

      // Outline box
      var outline = document.createElement('div');
      outline.className = NS + '-overlay';
      outline.dataset.index = index;
      outline.style.cssText = [
        'position: absolute',
        'top: ' + (rect.top + scrollY - 2) + 'px',
        'left: ' + (rect.left + scrollX - 2) + 'px',
        'width: ' + (rect.width + 4) + 'px',
        'height: ' + (rect.height + 4) + 'px',
        'outline: 2px solid ' + color,
        'outline-offset: -2px',
        'pointer-events: none',
        'z-index: ' + Z,
        'border-radius: 3px',
        'box-sizing: border-box',
        'transition: outline-color 0.2s',
      ].join(';');

      // Badge (number)
      var badge = document.createElement('div');
      badge.className = NS + '-badge';
      badge.dataset.index = index;
      badge.textContent = String(index + 1);
      badge.style.cssText = [
        'position: absolute',
        'top: ' + (rect.top + scrollY - 12) + 'px',
        'left: ' + (rect.left + scrollX - 6) + 'px',
        'width: 20px',
        'height: 20px',
        'border-radius: 50%',
        'background: ' + color,
        'color: #fff',
        'font-size: 11px',
        'font-weight: bold',
        'font-family: Arial, sans-serif',
        'display: flex',
        'align-items: center',
        'justify-content: center',
        'z-index: ' + Z,
        'pointer-events: none',
        'line-height: 1',
      ].join(';');

      // Label
      var label = document.createElement('div');
      label.className = NS + '-label';
      label.dataset.index = index;
      label.textContent = field.field_name || field.field_selector;
      label.style.cssText = [
        'position: absolute',
        'top: ' + (rect.top + scrollY - 12) + 'px',
        'left: ' + (rect.left + scrollX + 18) + 'px',
        'background: ' + color,
        'color: #fff',
        'font-size: 10px',
        'font-family: Arial, sans-serif',
        'padding: 2px 6px',
        'border-radius: 3px',
        'z-index: ' + Z,
        'pointer-events: none',
        'white-space: nowrap',
        'max-width: 200px',
        'overflow: hidden',
        'text-overflow: ellipsis',
      ].join(';');

      document.body.appendChild(outline);
      document.body.appendChild(badge);
      document.body.appendChild(label);

      _overlays.push({ outline: outline, badge: badge, label: label, el: el });
    });
  }

  /**
   * Generate a unique CSS selector for an element.
   */
  function generateSelector(el) {
    function isUnique(sel) {
      try {
        return document.querySelectorAll(sel).length === 1;
      } catch (e) {
        return false;
      }
    }

    if (el.id) return '#' + CSS.escape(el.id);

    // Prefer stable testing/accessibility attributes when available.
    var stableAttrs = ['data-testid', 'data-test', 'aria-label', 'name'];
    for (var i = 0; i < stableAttrs.length; i++) {
      var attr = stableAttrs[i];
      var attrVal = el.getAttribute(attr);
      if (!attrVal) continue;
      var tagWithAttr = el.tagName.toLowerCase() + '[' + attr + '="' + CSS.escape(attrVal) + '"]';
      if (isUnique(tagWithAttr)) return tagWithAttr;
    }

    if (el.name) {
      var tag = el.tagName.toLowerCase();
      var sel = tag + '[name="' + el.name + '"]';
      if (isUnique(sel)) return sel;
      if (el.type) {
        var typedSel = sel + '[type="' + CSS.escape(el.type) + '"]';
        if (isUnique(typedSel)) return typedSel;
      }
    }

    // Prefer form-scoped selectors when possible.
    var parentForm = el.tagName && el.tagName.toLowerCase() !== 'form' ? el.closest('form') : null;
    if (parentForm) {
      var formSel = generateSelector(parentForm);
      if (el.name) {
        var inFormByName = formSel + ' ' + el.tagName.toLowerCase() + '[name="' + CSS.escape(el.name) + '"]';
        if (isUnique(inFormByName)) return inFormByName;
      }
      if (el.type && (el.tagName.toLowerCase() === 'button' || el.tagName.toLowerCase() === 'input')) {
        var submitInForm = formSel + ' ' + el.tagName.toLowerCase() + '[type="' + CSS.escape(el.type) + '"]';
        var inFormCount = 0;
        try {
          inFormCount = document.querySelectorAll(submitInForm).length;
        } catch (e) {}
        if (inFormCount === 1) return submitInForm;
      }
    }

    // Fallback: build path
    var path = [];
    var current = el;
    while (current && current !== document.body) {
      var tag = current.tagName.toLowerCase();
      if (current.id) {
        return '#' + CSS.escape(current.id) + (path.length ? ' > ' + path.join(' > ') : '');
      }
      var parent = current.parentElement;
      if (parent) {
        var siblings = Array.from(parent.children).filter(function (c) {
          return c.tagName === current.tagName;
        });
        if (siblings.length > 1) {
          var idx = siblings.indexOf(current) + 1;
          tag += ':nth-of-type(' + idx + ')';
        }
      }
      path.unshift(tag);
      current = parent;
    }
    return path.join(' > ');
  }

  /**
   * Detect the purpose of a field from its attributes.
   */
  function detectFieldInfo(el) {
    var tag = el.tagName.toLowerCase();
    var type = el.type || (tag === 'select' ? 'select' : tag === 'textarea' ? 'textarea' : 'text');
    var name = el.name || el.id || '';
    var value = el.value || '';
    var placeholder = el.placeholder || '';

    // Try to detect purpose
    var purpose = 'other';
    var lowerName = (name + ' ' + placeholder).toLowerCase();
    if (/password|pwd|pass/i.test(lowerName)) purpose = 'password';
    else if (/email|e-mail/i.test(lowerName)) purpose = 'email';
    else if (/user|login|account/i.test(lowerName)) purpose = 'username';
    else if (/phone|tel|mobile/i.test(lowerName)) purpose = 'phone';
    else if (/search|query|q\b/i.test(lowerName)) purpose = 'search_query';

    // Detect available options for select, radio, and checkbox fields
    var options = null;

    if (tag === 'select') {
      // Extract all option values/texts from select element
      options = Array.from(el.options).map(function(opt) {
        return opt.value || opt.text;
      });
    } else if (type === 'radio' || type === 'checkbox') {
      // Find all radio/checkbox inputs with the same name
      var form = el.closest('form');
      var selector = 'input[name="' + el.name + '"][type="' + type + '"]';
      var siblings = form ? form.querySelectorAll(selector) : document.querySelectorAll(selector);
      options = Array.from(siblings).map(function(input) {
        return input.value || input.id;
      }).filter(function(v) { return v; });
    }

    return {
      tagName: tag,
      type: type,
      name: name,
      value: value,
      purpose: purpose,
      placeholder: placeholder,
      options: options,
    };
  }

  // ---- Prevent form submission during editing ----
  function handleSubmit(e) {
    e.preventDefault();
    e.stopPropagation();
    console.log('[FormBot] Form submission prevented during editing mode');
  }

  // ---- Click handler ----
  function handleClick(e) {
    var target = e.target;
    // Skip our own overlays
    if (target.className && typeof target.className === 'string' && target.className.indexOf(NS) !== -1) return;

    e.preventDefault();
    e.stopPropagation();

    // Auto-mode logic: check if clicked element is already a tracked field
    var clickedIndex = -1;
    for (var i = 0; i < _fields.length; i++) {
      var el = getElement(_fields[i].field_selector);
      if (el && (el === target || el.contains(target))) {
        clickedIndex = i;
        break;
      }
    }

    // If clicked on an existing field → auto-select (even if mode was 'add')
    if (clickedIndex >= 0) {
      var f = _fields[clickedIndex];
      if (window.__formbot_onFieldSelected) {
        window.__formbot_onFieldSelected(JSON.stringify({
          index: clickedIndex,
          selector: f.field_selector,
          name: f.field_name,
          type: f.field_type,
          purpose: f.field_purpose || '',
          value: f.preset_value || '',
        }));
      }
      return;
    }

    // If in explicit 'remove' mode and clicked on a non-field, ignore
    if (_mode === 'remove') return;

    // Otherwise, try to add the clicked element as a new field (auto-add)
    // Find closest interactive form element — ignore non-interactive elements
    var formEl = target.closest('input, select, textarea, button, [contenteditable="true"]');
    if (!formEl) return;

    var selector = generateSelector(formEl);

    // Check if this selector already exists (duplicate prevention)
    var isDuplicate = false;
    for (var i = 0; i < _fields.length; i++) {
      if (_fields[i].field_selector === selector) {
        isDuplicate = true;
        break;
      }
    }

    if (isDuplicate) {
      // Flash a warning (orange outline)
      var origOutline = formEl.style.outline;
      formEl.style.outline = '3px solid #FF9800';
      setTimeout(function () {
        formEl.style.outline = origOutline;
      }, 800);
      console.log('[FormBot] Field already added:', selector);
      return;
    }

    var info = detectFieldInfo(formEl);

    // Detect parent <form> element
    var parentForm = formEl.closest('form');
    var formSelector = parentForm ? generateSelector(parentForm) : '';
    // Also detect submit button within the form
    var submitSelector = '';
    if (parentForm) {
      var submitBtn = parentForm.querySelector('button[type="submit"], input[type="submit"], button:not([type])');
      if (submitBtn) submitSelector = generateSelector(submitBtn);
    }

    if (window.__formbot_onFieldAdded) {
      window.__formbot_onFieldAdded(JSON.stringify({
        selector: selector,
        tagName: info.tagName,
        type: info.type,
        name: info.name,
        value: info.value,
        purpose: info.purpose,
        form_selector: formSelector,
        submit_selector: submitSelector,
      }));
    }
  }

  // ---- Public API ----

  window[NS] = {
    init: function (fieldsJson) {
      _fields = typeof fieldsJson === 'string' ? JSON.parse(fieldsJson) : fieldsJson;
      _mode = 'select';
      document.addEventListener('click', handleClick, true);
      document.addEventListener('submit', handleSubmit, true);
      createOverlays();
      attachInputListeners();
    },

    command_updateFields: function (fieldsJson) {
      _fields = typeof fieldsJson === 'string' ? JSON.parse(fieldsJson) : fieldsJson;
      createOverlays();
      attachInputListeners();
    },

    command_setMode: function (mode) {
      _mode = mode;
      // Update cursor
      document.body.style.cursor =
        mode === 'add' ? 'crosshair' :
        mode === 'remove' ? 'not-allowed' : 'pointer';
    },

    command_focusField: function (index) {
      if (index < 0 || index >= _fields.length) return;
      var el = getElement(_fields[index].field_selector);
      if (!el) return;

      el.scrollIntoView({ behavior: 'smooth', block: 'center' });

      // Flash highlight
      var overlay = _overlays[index];
      if (overlay && overlay.outline) {
        overlay.outline.style.outlineWidth = '4px';
        overlay.outline.style.outlineColor = '#FFD600';
        setTimeout(function () {
          var color = getColor(_fields[index].field_type);
          overlay.outline.style.outlineWidth = '2px';
          overlay.outline.style.outlineColor = color;
        }, 1000);
      }
    },

    command_testSelector: function (selector) {
      try {
        var matches = document.querySelectorAll(selector);
        var found = matches.length > 0;

        // Visual flash
        matches.forEach(function (el) {
          var origOutline = el.style.outline;
          el.style.outline = found ? '3px solid #4CAF50' : '3px solid #F44336';
          setTimeout(function () {
            el.style.outline = origOutline;
          }, 1500);
        });

        return { found: found, matchCount: matches.length };
      } catch (e) {
        return { found: false, matchCount: 0, error: e.message };
      }
    },

    command_fillField: function (index, value) {
      if (index < 0 || index >= _fields.length) return;
      var el = getElement(_fields[index].field_selector);
      if (!el) return;

      el.value = value;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    },

    command_readFieldValue: function (index) {
      if (index < 0 || index >= _fields.length) return '';
      var el = getElement(_fields[index].field_selector);
      return el ? el.value : '';
    },

    command_cleanup: function () {
      removeInputListeners();
      removeOverlays();
      document.removeEventListener('click', handleClick, true);
      document.removeEventListener('submit', handleSubmit, true);
      document.body.style.cursor = '';
      _fields = [];
      _mode = 'select';
    },

    getFields: function () {
      return _fields;
    },

    getMode: function () {
      return _mode;
    },
  };
})();
