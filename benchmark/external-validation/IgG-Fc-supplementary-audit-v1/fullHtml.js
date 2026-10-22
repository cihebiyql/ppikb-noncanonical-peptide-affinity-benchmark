$(document).ready(function () {
    $('[data-toggle="tooltip"]').on('shown.bs.tooltip', function () {
        MathJax.Hub.Queue(["Typeset",MathJax.Hub]);
    });
})
$('[data-toggle="tooltip"]').tooltip('destroy');
$('[data-toggle="tooltip"]').tooltip({
	container:'#article-overiew-abstract-wrap',
	placement:function(tip,element) {
		var Height = $(element).height();
		if (Height > 19) {
			return "right";
		} else {
			return "bottom";
		}
	}
});