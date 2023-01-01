from django import template


register = template.Library()


def vowels_down(word):
    vowels = 'аоеёэыиуюя'
    result = ''
    for ch in word:
        if ch in vowels:
            result += ch
        else:
            result += ch.upper()
    return result


register.filter('vowelsDOWN', vowels_down)


if __name__ == '__main__':
    print(vowels_down('Привет мир и прощай!'))
