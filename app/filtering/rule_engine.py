class RuleEngine:
    def __init__(self, rules):
        """
        rules: список правил, каждое правило - словарь:
            {
                'words': ['слово1', 'слово2', ...],
                'operator': 'AND' или 'OR'
            }
        """
        self.rules = rules

    def match(self, text):
        """Возвращает True, если текст соответствует хотя бы одному правилу."""
        for rule in self.rules:
            words = rule.get('words', [])
            operator = rule.get('operator', 'OR').upper()
            if operator == 'AND':
                # Все слова должны присутствовать
                if all(w in text for w in words):
                    return True
            else:  # OR
                # Хотя бы одно слово должно присутствовать
                if any(w in text for w in words):
                    return True
        return False