// Win95 menu bars, shared by the editor and the Operational Centre. A menu closes when the
// operator picks from it, clicks or tabs elsewhere, or presses Escape. A menu button with
// data-command presses the control with that id, and is enabled only while that control is.
(() => {
  const openMenu = () => document.querySelector('.menubar details[open]');

  function close(menu, restoreFocus) {
    menu.open = false;
    if (restoreFocus && !document.querySelector('dialog[open]')) {
      menu.querySelector('summary').focus();
    }
  }

  document.addEventListener('toggle', event => {
    if (!event.target.matches('.menubar details') || !event.target.open) return;
    for (const button of event.target.querySelectorAll('[data-command]')) {
      const target = document.getElementById(button.dataset.command);
      if (target) button.disabled = target.disabled;
    }
  }, true);

  document.addEventListener('click', event => {
    const menu = openMenu(), button = event.target.closest('button');
    if (!menu || (menu.contains(event.target) && !button)) return;
    if (!button || !menu.contains(button)) return close(menu, false);
    if (button.dataset.command) document.getElementById(button.dataset.command)?.click();
    close(menu, true);
  });

  document.addEventListener('focusin', event => {
    const menu = openMenu();
    if (menu && !menu.closest('.menubar').contains(event.target)) close(menu, false);
  });

  document.addEventListener('keydown', event => {
    const menu = openMenu();
    if (event.key !== 'Escape' || !menu) return;
    // The editor's own Escape would drop the line being drawn.
    event.stopPropagation();
    close(menu, true);
  });
})();
