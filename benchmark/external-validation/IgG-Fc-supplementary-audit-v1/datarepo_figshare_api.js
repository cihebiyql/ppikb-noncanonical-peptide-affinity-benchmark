$(document).ready(function () {

	$('.navbar-fixed-top').css('z-index','1001');
	$('.preview-nav').css('z-index','1002');

	// 詳細ラベル付与
	var LABEL_DATA_REPOSITORY_DETAIL = $("#labelDataRepositoryDetail").val();
	$(".data-repo-detail-title").each(function() {
		$(this).text(LABEL_DATA_REPOSITORY_DETAIL);
	});

	var searching = '<div class = "loading-view"style="height:40px; text-align: center;"><img src="$!base/web/images/new_update/ajax-loader.gif" alt=""></div>'

// statement に含まれるリンクに属性を追加
	$('.repo-statement').find('a').each(function() {
		$(this).attr('target', '_blank');
		$(this).attr('rel', 'noopener noreferrer');
		$(this).attr('class', 'bluelink-style');
		$(this).append('<span class="fa fa-external-link external-link-icon"></span>');
	});

// プレビューを表示
	var doiTag = $('#fig-doi').find("a")
	var doiUrl = $(doiTag).text();
	var doi = "";
	if (doiUrl) {
		doi = doiUrl.replace(/http(s)*:\/\/doi.org\//, "");
	}

	// toggle the component with class accordion_body
	$(".repo_accordion_head").click(function () {

		if ($(this).next(".accordion_body").is(':visible')) {
			$(this).next(".accordion_body").slideUp(300);
			$(this).addClass("plus-icn");
			$(this).removeClass("minus-icn");
		} else {
			$(this).next(".accordion_body").slideDown(300);
			$(this).removeClass("plus-icn");
			$(this).addClass("minus-icn");
		}
	});

// FIGAPI-002
	window.figshare.load("jstage", function (FilesViewerWidget) {
		var el = document.getElementById("figshare-widget");
		if (el) {
			var widget = new FilesViewerWidget({
				version: "3",
				width: 650,
				height: 450,
				breakPoint: 550,
				showStats: true,
				showPageInfo: true,
				showShareButton: true,
				showFileDetails: true,
				article: {
					resourceDOI: doi
				},
			});

			widget.on("mount", function() {
			});
			widget.on("filesError", function() {
			});
			widget.initialize();
			widget.mount(el);
		}
	});
});

// FIGAPI-001
	var detail = [];

	function detailSearch(element) {
		var target = $(element).next(".accordion_body");
		var pIndex = target.attr("pIndex");
		if (!detail[pIndex]) {
			detail[pIndex] = [];
		}
		if (detail[pIndex][target.attr("index")]) {
			return;
		}
		target.append(searching);
		articleSearchPre(target);
	}

	function requestEnd(target) {
		detail[target.attr("pIndex")][target.attr("index")] = true;
		$('.loading-view').remove();
	}
	function errSet(target) {
		var errEl = $(target.find(".datarepo-error"));
		errEl.text($("#labelDataRepositoryNoDetail").val());
		errEl.show();
		requestEnd(target);
	}

	function articleSearchPre(target) {
		$.ajax({
			cache: false,
			type: 'GET',
			// リリース前に本番用URLに直す
			url: $("#figshareArticleSearchUrl").val() + encodeURI("?page_size=10&order=published_date&order_direction=desc&doi=" + target.attr("doi")),
			dataType: 'html',
			contentType:'text/html',
			success: function(strJson) {
				var res = JSON.parse(strJson)[0];
				if (!res) {
					errSet(target);
					return;
				}
				var id = res.id;
				articleDetail(target, id);
			},
			error: function(e) {
				errSet(target);
			},
			complete : function() {
				requestEnd(target);
			}
		});
	}

	function articleDetail(target, id) {
		$.ajax({
			cache: false,
			type: 'GET',
			url: encodeURI($("#figshareArticleSearchUrl").val() + "/" + id),
			dataType: 'html',
			contentType:'text/html',
			success: function(strJson) {
				var res = JSON.parse(strJson);
				var pubLishedDateJST = "";
				if (res.published_date.slice(-1) === "Z") {
					var publishedDateUTC = new Date(res.published_date);
					publishedDateUTC.setTime(publishedDateUTC.getTime() + 1000*60*60*9);
					pubLishedDateJST = publishedDateUTC.getUTCFullYear()
					+ '-' + ('0' + (publishedDateUTC.getUTCMonth() + 1)).slice(-2)
					+ '-' + ('0' + publishedDateUTC.getUTCDate()).slice(-2);
				} else {
					pubLishedDateJST = "published dateがJ-STAGE Dataから取得できませんでした。";
				}
				var title = res.title;
				var authors = res.authors;
				var joinAuthors = "";
				for (i in authors) {
					if (joinAuthors.length > 0) {
						joinAuthors = joinAuthors + ", ";
					}
					joinAuthors = joinAuthors + authors[i].full_name;
				}

				target.append("<p>published date:" + pubLishedDateJST + "</p>");
				target.append("<p>title:" + title + "</p>");
				target.append("<p>authors:" + joinAuthors + "</p>");
			},
			error: function(e) {
			}
		});
	}