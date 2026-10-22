//**** NAVIGATION TO DROPDOWN :: START ****//
jQuery(document).ready(function(){
try {
	$('#article-overiew-section-links > ul').navToSelect({
		// override: add anchor position adjust + animate scroll
		// see:      https://github.com/amazingSurge/jquery-navToSelect
		onChange: function() {
			//get selected item (li object is hidden)
			var $selected_option = $(this).find("option:selected");
			var $selected_li = $('#article-overiew-section-links > ul > li').eq(this.options.selectedIndex);

			// "#xxxx"  ->  linkable: true
			// "#"      ->  linkable: false
			if ($selected_option.data('linkable') !== false) {

				// set "#xxxxx"
				var elementClick = this.value;
				var elementClass = $selected_li.find("a").eq(0).attr("class");
				
				var fixedHeaderHeight = 0;
				if ($('.navbar-fixed-top').length) {
					fixedHeaderHeight = $('.navbar-fixed-top').eq(0).outerHeight();
				}

				// set position adjust
				// ** "topLevel" is <li> attribute class **
				var headerHight = 0
				if (elementClass != undefined && elementClass.match(/toplevel/)) {
					headerHight = 0;
				} else {
					headerHight = fixedHeaderHeight + 40;
				}
				var destination = $(elementClick).offset().top - headerHight;

				// animate scroll
				$("html:not(:animated),body:not(:animated)").animate({ scrollTop: destination }, /* settings.speed = */ 1100, function() {
				});

				history.pushState(null, null, location.pathname + location.search + elementClick);
			}
			return false;
		}
	});
} catch (e) {console.log("Exception : " + e);}

});
//**** NAVIGATION TO DROPDOWN :: END ****//
