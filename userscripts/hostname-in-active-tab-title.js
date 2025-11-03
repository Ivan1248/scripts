// ==UserScript==
// @name        Hostname in active tab title
// @namespace   Userscripts
// @match       *://*/*
// @grant       none
// @version     1.0
// @author      Ivan Grubišić and ChatGPT
// @description Modify document title with user-defined prefix and suffix, depending on tab visibility.
// ==/UserScript==

(function () {
    'use strict';

    const prefix = (location.hostname + ' - ').trimStart(); // User-defined prefix
    const suffix = ''.trimEnd(); // User-defined suffix
    // const ignored_titles = [''];  // PDF viewer
    // const isPDF=true;

    function consistsOnlyOfTrimmedAffix(title) {
        return title == (prefix + suffix).trim();
    }

    function containsAffixes(title) {
        return title.startsWith(prefix) && title.endsWith(suffix) || consistsOnlyOfTrimmedAffix(title);
    }

    function removeAffixes(title) {
        return containsAffixes(title) ? title.slice(prefix.length, title.length - suffix.length)
                                      : consistsOnlyOfTrimmedAffix(title) ? ''
                                                                          : title;
    }

    function getTitleWithoutAffixes(title) {
        let titleWithoutAffixes = removeAffixes(title);
        return titleWithoutAffixes == '' ? location.pathname : titleWithoutAffixes;
    }

    function getPDFTitleElement() {
      return document.querySelector('head').querySelector('title'); //document.querySelector('pdf-viewer').shadowRoot.querySelector('viewer-toolbar').shadowRoot.getElementById('title');
    }

    function getPDFTitle() {
      return document.getElementsByClassName("gsr-tb-title")[0].innerText;
      return getPDFTitleElement().innerHTML;
    }

    function maybeUpdateTitle() {
        let title = document.title;
        try {
            title = getPDFTitle();
        } catch (error) {
            //alert(error);
            title = document.title;
        }

        const titleWithoutAffixes = getTitleWithoutAffixes(title);

        if (document.hidden) {
            if (containsAffixes(title)) { // Remove affixes
                document.title = titleWithoutAffixes == '' ? location.pathname
                                                           : titleWithoutAffixes;
            }
        } else {
            if (!containsAffixes(title)) { // Add affixes
                document.title = prefix + titleWithoutAffixes + suffix;
            }
        }
    }

    // Initial update
    //maybeUpdateTitle();
    //setTimeout(maybeUpdateTitle, 100);
    for (let i = 0; i < 4; i++){
        setTimeout(maybeUpdateTitle, 1000 * 4**i);
    }
    // Detect changes to the title and update accordingly
    let titleObserver = new MutationObserver((mutations, observer) => maybeUpdateTitle());
    // 'title' instead of 'head' works in most cases, but not always
    titleObserver.observe(document.querySelector('head'),
                          { subtree: true, childList: true });

    // Handle tab visibility changes
    document.addEventListener('visibilitychange', (event) => maybeUpdateTitle());
})();
