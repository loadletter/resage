// ==UserScript==
// @name           4chan - Highlight all sage posts v2
// @namespace      resage (https://github.com/loadletter/resage)
// @description    Finds saged posts and changes the email field from the default blue colour to red. This is useful as you can distinguish posts with sage. 
// @include        http://*.4chan.org/*/res/*
// @include        https://*.4chan.org/*/res/*
// @grant          GM_xmlhttpRequest
// @updateURL      https://github.com/loadletter/resage/raw/master/resage.user.js
// ==/UserScript==

/*
* RIP 2008-2013
* Original script http://userscripts.org/scripts/review/36554
*/

var workernumber = 2; /* load balancing pro */
var serverurl = "http://resage-" + Math.floor((Math.random() * workernumber) + 1) + ".herokuapp.com/api";
var spliturl = document.URL.split(/4chan.org\/([\d\w]{1,3})\/res\/([0-9]+)$/);
var supportedboards = ['a', 'jp'];
var board = spliturl[1];
var thread = spliturl[2];
var lastmodified = "";
var sagelist = [];
var cooldown = false;
var postqueue = [];

 
function ArrInclude(arr, obj)
{
    return (arr.indexOf(obj) != -1);
}

function GetPostsFromAPI(e)
{
    var headers_tosend = {
			'User-agent': navigator.userAgent,
			'Accept': 'application/json',
    };
    
    var listmodified = false;
    
    if(lastmodified != "")
    {
        headers_tosend['If-Modified-Since'] = lastmodified;
    }
    
    console.log("Tosend %s", JSON.stringify(headers_tosend));
    
    GM_xmlhttpRequest({
        method: 'GET',
        url: serverurl + '/' + board + '/' + thread,
        headers: headers_tosend,
        onload: function(responseDetails) {
            switch(responseDetails.status)
			{
				case 200: {
                    console.log("Got data: %s", responseDetails.responseHeaders);
                    lastmodified = responseDetails.responseHeaders.split(/(^|\n)Last-Modified: ([\w\d\s:,]+ GMT)/)[2];
                    sagelist = JSON.parse(responseDetails.responseText);
                    listmodified = true;
                    console.log("Lastmod: %s", lastmodified);
                }
                break;
                case 304:
                    console.log("Data not modified");
                break;
                default:
                    console.log("Error %i", responseDetails.status);
			}
            
            if(listmodified && e == undefined)
            {
                while((pst = postqueue.pop()) != undefined)
                {
                    console.log("runnnig from queue");
                    Array.forEach(pst.getElementsByClassName("postInfo desktop"), HighlightIfSage);
                }
                return;
            }
            
            if(listmodified)
            {
                Array.forEach(e.getElementsByClassName("postInfo desktop"), HighlightIfSage);
            }
		}
	});
}

function HighlightIfSage(a)
{
    if(ArrInclude(sagelist, parseInt((a.id.slice(2)))))
    {
        a.getElementsByClassName("name")[0].style.color = "red";
        a.getElementsByClassName("name")[0].style.fontStyle = "italic";
    }
}

/*
 * 4chan X's thread expansion and thread updater
 */
 
function OnDOMNodeInserted(e)
{
    if(e.target.nodeName == "DIV" && e.target.getElementsByClassName("postInfo desktop").length > 0)
    {
        postqueue.push(e.target);   
        if(cooldown) {
            console.log("on cooldown");

        } else {
            console.log("running from ondomnodeinserted");
            console.log("Mod 2: %s", lastmodified);
            cooldown = true;
            setTimeout(function() {GetPostsFromAPI(); cooldown = false;}, 12000);
        }
    }
}

if(ArrInclude(supportedboards, board)) {
    GetPostsFromAPI(document);
    console.log("running from load");
    document.body.addEventListener("DOMNodeInserted", OnDOMNodeInserted, false);
}
