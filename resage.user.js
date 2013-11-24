// ==UserScript==
// @name           4chan - Highlight all sage posts
// @namespace      resage (https://github.com/loadletter/resage)
// @description    Finds saged posts and changes the email field from the default blue colour to red. This is useful as you can distinguish posts with sage. 
// @include        http://*.4chan.org/*
// @include        https://*.4chan.org/*
// @grant          GM_xmlhttpRequest
// ==/UserScript==

/*
* RIP 2008-2013
* Original script http://userscripts.org/scripts/review/36554
*/

var serverurl = "http://resage.herokuapp.com/";

/*function transmit(obj)
{
	GM_xmlhttpRequest({
		method: 'GET',
		url: 'http://www.yoursite.org/datagatherer/',
		headers: {
			'User-agent': 'Mozilla/4.0 (compatible) Greasemonkey',
			'Accept': 'application/json',
			'Content-type': 'application/x-www-form-urlencoded'
		},
		data: 'json=' + JSON.stringify(obj),
		onload: function(responseDetails) {
			if(responseDetails.status == 200)
			{
				alert("Got a good response!");
			}
		}
	});
}*/

function HighlightIfSage(a)
{
    if (a.href.indexOf("mailto:") == 0) 
    {
        if (a.href.toLowerCase().indexOf("sage") != -1)
        {
            a.style.color = "red";
            a.style.fontStyle = "italic";
        }
    }
}

Array.forEach(document.getElementsByTagName('A'), HighlightIfSage);

/*
 * 4chan X's thread expansion and thread updater
 */
 
function OnDOMNodeInserted(e)
{
    if(e.target.nodeName == "DIV")
    {
        Array.forEach(e.target.getElementsByTagName('A'), HighlightIfSage);
    }
}

document.body.addEventListener("DOMNodeInserted", OnDOMNodeInserted, false);
