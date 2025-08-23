import questionary


def extended_choice(*args, **kwargs):
    hide_menu_items = None #APP_CONFIG.hide_menu_items
    if hide_menu_items and kwargs.get("title", "") in hide_menu_items:
        return None
    else:
        return questionary.Choice(*args, **kwargs)
