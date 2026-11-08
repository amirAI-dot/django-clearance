/*
 * The rule builder: add and remove conditions. Without this script the page
 * still works, offering a few empty conditions at a time; with it, as many as
 * are needed. No build step, no library.
 */
(function () {
  'use strict';

  function ready() {
    var form = document.getElementById('clearance-rule');
    var add = document.getElementById('clearance-add');
    if (!form || !add) {
      return;
    }
    var body = form.querySelector('.clearance-conditions tbody');

    function rows() {
      return body.querySelectorAll('tr.clearance-condition');
    }

    function arm(row) {
      var remove = row.querySelector('.clearance-remove');
      remove.hidden = false;
      remove.addEventListener('click', function () {
        if (rows().length > 1) {
          row.remove();
        } else {
          row.querySelectorAll('input').forEach(function (input) { input.value = ''; });
        }
      });
    }

    rows().forEach(arm);
    add.hidden = false;
    add.addEventListener('click', function () {
      var all = rows();
      var row = all[all.length - 1].cloneNode(true);
      row.querySelectorAll('input').forEach(function (input) { input.value = ''; });
      row.querySelectorAll('select').forEach(function (select) { select.selectedIndex = 0; });
      body.appendChild(row);
      arm(row);
      row.querySelector('input[name="field"]').focus();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ready);
  } else {
    ready();
  }
}());
