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
var spliturl = document.URL.split(/4chan.org\/([\d\w]{1,3})\/res\/([0-9]+)$/);
var supportedboards = ['a'];
var board = spliturl[1];
var thread = spliturl[2];
var lastmodified = "";
var sagelist = [];


/*TODO:
 * eventlistener -->\
 *                   |--> getdatafromAPI --> if arrainclude(supportedboards, board) --> highlight from sagelist
 * pageload ------->/
 * */
 
function arrinclude(arr, obj) {
    return (arr.indexOf(obj) != -1);
}

function getdatafromAPI()
{
    var headers_tosend = {
			'User-agent': navigator.userAgent,
			'Accept': 'application/json',
    };
    
    var listmodified = false;
    
    if(lastmodified != "") {
        headers_tosend['If-Modified-Since'] = lastmodified;
    }
    
    GM_xmlhttpRequest({
        method: 'GET',
        url: serverurl + '/' + board + '/' + thread,
        headers: headers_tosend,
        onload: function(responseDetails) {
            switch(responseDetails.status)
			{
				case 200:
                    console.log("Got data");
                    lastmodified = responseDetails.responseHeaders['Last-Modified'];
                    sagelist = JSON.parse(responseDetails.responseText);
                    listmodified = true;
                break;
                case 304:
                    console.log("Data not modified");
                break;
                default:
                    console.log("Error %i", responseDetails.status);
			}
            
            if(listmodified) {
                //execute somethings that executes runs the highlight code
            }
        
		}
	});
}

function HighlightIfSage(a)
{
    /*if (a.href.indexOf("mailto:") == 0) 
    {
        if (a.href.toLowerCase().indexOf("sage") != -1)
        {
            a.style.color = "red";
            a.style.fontStyle = "italic";
        }
    }*/
    if(arrinclude(sagelist, parseInt((a.id.slice(2)))))
    {
        a.getElementsByClassName("name")[0].style.color = "red";
        a.getElementsByClassName("name")[0].fontStyle = "italic";
    }
    /* this should  work */ 
}

Array.forEach(document.getElementsByClassName("postContainer replyContainer"), HighlightIfSage);

/*
 * 4chan X's thread expansion and thread updater
 */
 
function OnDOMNodeInserted(e)
{
    if(e.target.nodeName == "DIV")
    {
        Array.forEach(e.target.getElementsByClassName("postContainer replyContainer"), HighlightIfSage);
    }
}

document.body.addEventListener("DOMNodeInserted", OnDOMNodeInserted, false);
