def user_role(request):
    """
    Добавляет в контекст переменную user_role для отображения роли пользователя в хедере.
    """
    if request.user.is_authenticated:
        if request.user.is_superuser:
            role = 'Администратор'
        elif request.user.role and 'committee' in request.user.role.name.lower():
            role = 'Комитет образования'
        elif request.user.institution:
            role = 'Директор'
        else:
            role = 'Пользователь'
    else:
        role = None
    return {'user_role': role}