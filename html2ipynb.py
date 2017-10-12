# html to ipynb
import sys
import re

def downloadFile(URL=None):
    import httplib2
    h = httplib2.Http(".cache")
    resp, content = h.request(URL, "GET")
    return content

def extract_cells(html):
    r = re.compile("((?:<h\d|<div)[^%]*?)(?=<h\d|<div)")
    return r.findall(html)

def refine_cell(html, base_url):
    def multireplace(string, replacements):
        """
        Given a string and a replacement map, it returns the replaced string.
        :param str string: string to execute replacements on
        :param dict replacements: replacement dictionary {value to find: value to replace}
        :rtype: str
        """
        # Place longer ones first to keep shorter substrings from matching where the longer ones should take place
        # For instance given the replacements {'ab': 'AB', 'abc': 'ABC'} against the string 'hey abc', it should produce
        # 'hey ABC' and not 'hey ABc'
        substrs = sorted(replacements, key=len, reverse=True)

        # Create a big OR regex that matches any of the substrings to replace
        regexp = re.compile('|'.join(map(re.escape, substrs)))

        # For each match, look up the new string in the replacements
        string = regexp.sub(lambda match: replacements[match.group(0)], string)
        imgregexp = re.compile(r'((<img .*?src=")(.*?)(" ?)(?:.*?alt=".*?")?(.*>))')        
        string = imgregexp.sub(r'\1\n\2'+base_url+r'/\3\4 alt="\3" \5', string)
        return string

    return multireplace(html, { 
        r'\(' : '$', 
        r'\)' : '$', 
        '<pre><code class="python">' : "``` python\n", 
        '</code></pre>' : "```",
        r'((<img .*?src=")(.*)(".*>))' : r"\1\n\2"+base_url+r"/\3\4"})

def create_ipynb(cells):
    import json
    all = ["{ \"cells\" : [\n"]
    for c in cells:
        all.append('{ "cell_type": "markdown", "metadata": {}, "source": [ ')
        all.append(json.dumps(c))
        all.append(" ] }")
        all.append(",\n")
    all[-1] = "\n],"
    all.append("""      
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3", "language": "python", "name": "python3"
            },
            "language_info": {
                "codemirror_mode": { "name": "ipython", "version": 3 },
                "file_extension": ".py", "mimetype": "text/x-python",
                "name": "python", "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3", "version": "3.6.1"
            }
        },
        "nbformat": 4, "nbformat_minor": 2
        }""")    
    return "".join(all)

def main():
    if len(sys.argv) < 2:
        print("usage: html2ipynb url [outfile]")
    url = sys.argv[1]
    out = ""
    base_url, name = url.rsplit('/', 1)
    if len(sys.argv) == 2:
        out = name + ".ipynb"
    else:
        out = sys.argv[2]
        if not out.endswith(".ipynb"):
            out += ".ipynb"
    print(url)
    html = downloadFile(url)
    html = html.decode("UTF-8", errors="ignore")
    raw_cells = extract_cells(html)
    refined_cells = [refine_cell(c, base_url) for c in raw_cells]
    ipynb = create_ipynb(refined_cells)

    f = open(out, "wb")
    f.write(ipynb.encode("utf-8", errors="ignore"))
    f.close()

    print('"'+url+'" converted to "'+out+'"')

main()
