"""Parse a bounded JavaScript data literal; never evaluate JavaScript code."""
import re


class LiteralParser:
    def __init__(self, text):
        self.text, self.pos = text, 0

    def space(self):
        while self.pos < len(self.text):
            match = re.match(r'\s+|//[^\n]*(?:\n|$)|/\*[\s\S]*?\*/', self.text[self.pos:])
            if not match:
                break
            self.pos += match.end()

    def char(self, expected):
        self.space()
        if not self.text.startswith(expected, self.pos):
            raise ValueError('Expected %r at offset %d' % (expected, self.pos))
        self.pos += len(expected)

    def string(self):
        quote = self.text[self.pos]
        self.pos += 1
        out = []
        escapes = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'f': '\f', 'v': '\v', '0': '\0'}
        while self.pos < len(self.text):
            char = self.text[self.pos]
            self.pos += 1
            if char == quote:
                return ''.join(out)
            if char != '\\':
                out.append(char)
                continue
            if self.pos == len(self.text):
                break
            char = self.text[self.pos]
            self.pos += 1
            if char in ('u', 'x'):
                size = 4 if char == 'u' else 2
                digits = self.text[self.pos:self.pos+size]
                if not re.fullmatch('[0-9a-fA-F]{%d}' % size, digits):
                    raise ValueError('Invalid string escape')
                out.append(chr(int(digits, 16)))
                self.pos += size
            else:
                out.append(escapes.get(char, char))
        raise ValueError('Unterminated string')

    def value(self, depth=0):
        if depth > 30:
            raise ValueError('Literal nesting exceeds limit')
        self.space()
        if self.pos >= len(self.text):
            raise ValueError('Missing literal')
        char = self.text[self.pos]
        if char in ('"', "'"):
            return self.string()
        if char in '[{':
            self.pos += 1
            closing = ']' if char == '[' else '}'
            result = [] if char == '[' else {}
            while True:
                self.space()
                if self.text.startswith(closing, self.pos):
                    self.pos += 1
                    return result
                if char == '{':
                    if self.text[self.pos] in ('"', "'"):
                        key = self.string()
                    else:
                        match = re.match(r'[A-Za-z_$][\w$]*', self.text[self.pos:])
                        if not match:
                            raise ValueError('Invalid object key')
                        key = match.group(0)
                        self.pos += match.end()
                    if key in result:
                        raise ValueError('Duplicate object key: ' + key)
                    self.char(':')
                    result[key] = self.value(depth+1)
                else:
                    result.append(self.value(depth+1))
                self.space()
                if self.text.startswith(',', self.pos):
                    self.pos += 1
                elif not self.text.startswith(closing, self.pos):
                    raise ValueError('Expected comma or closing delimiter')
        match = re.match(r'-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?', self.text[self.pos:])
        if match:
            self.pos += match.end()
            number = match.group(0)
            return float(number) if any(c in number for c in '.eE') else int(number)
        for keyword, value in [('true', True), ('false', False), ('null', None)]:
            if re.match(keyword+r'\b', self.text[self.pos:]):
                self.pos += len(keyword)
                return value
        raise ValueError('Only static data literals are supported at offset %d' % self.pos)


def extract_assignment(text, variable):
    parser = LiteralParser(text)
    parser.space()
    parser.char('window.' + variable)
    parser.char('=')
    result = parser.value()
    parser.space()
    if parser.pos < len(text):
        parser.char(';')
    parser.space()
    if parser.pos != len(text):
        raise ValueError('Unexpected code after data assignment')
    return result


def extract_universities(text):
    parser = LiteralParser(text)
    parser.space()
    parser.char('window.UNIVERSITIES')
    parser.space()
    if text.startswith('=', parser.pos):
        parser.char('=')
        result = parser.value()
        if not isinstance(result, list):
            raise ValueError('Expected university array')
    else:
        parser.char('.push(')
        result = []
        while True:
            parser.space()
            if text.startswith(')', parser.pos):
                parser.pos += 1
                break
            result.append(parser.value())
            parser.space()
            if text.startswith(',', parser.pos):
                parser.pos += 1
            elif not text.startswith(')', parser.pos):
                raise ValueError('Invalid push data')
    parser.space()
    if parser.pos < len(text):
        parser.char(';')
    parser.space()
    if parser.pos != len(text):
        raise ValueError('Unexpected code after university data')
    return result
