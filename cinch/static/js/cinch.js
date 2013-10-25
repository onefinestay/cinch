var Clinch = Clinch || {};

Clinch.AttachEvents = function() {
    $("#filter-username").click(function(){
        Clinch.FilterByUsername();
    });
    $("#filter-all").click(function(){
        Clinch.FilterAll($(this));
    });
    $(".filter-project").click(function(){
        Clinch.FilterByProject($(this));
    });
};

Clinch.FilterAll = function() {
    Clinch.SwapClass($("#filter-all"), "filter-off", "filter-on");
    Clinch.SwapClass($("#filter-username"), "filter-on", "filter-off");
    $(".pr-hidden").removeClass("pr-hidden");
    Clinch.Mason();
};

Clinch.FilterByUsername = function() {
    Clinch.SwapClass($("#filter-all"), "filter-on", "filter-off");
    Clinch.SwapClass($("#filter-username"), "filter-off", "filter-on");
    $(".pull_request").each(function(){
        if ($(this).data("gh-user") != Clinch.GHUsername)
            $(this).addClass("pr-hidden");
        else
            $(this).removeClass("pr-hidden");
    });
    Clinch.Mason();
};

Clinch.FilterByProject = function(selection) {
    var selected_project = $(selection).data("projectname");
    // Change the highlighting
    Clinch.SwapClass($("#filter-all"), "filter-on", "filter-off");
    Clinch.SwapClass($(selection), "filter-off", "filter-on");
    $("#filter-project").find("a").each(function(){
        if ($(this).data("projectname") != selected_project)
            Clinch.SwapClass($(this), "filter-on", "filter-off");
        else
            Clinch.SwapClass($(this), "filter-off", "filter-on");
    });
    // Change the panel display - depending on user/all selections
    if (selected_project == "all"){
        $(".pull_request").each(function(){
            $(this).removeClass("pr-hidden");
        });
    }
    else{
        $(".pull_request").each(function(){
            if ($(this).data("project") == selected_project)
                $(this).removeClass("pr-hidden");
            else
                $(this).addClass("pr-hidden");
        });
    }
    Clinch.Mason();
};

Clinch.Mason = function() {
    // Replot the layout, animate between states
    var $container = $('#pr-container');
    $container.masonry();
};

Clinch.SwapClass = function(elm, from, to) {
    // Change one class for another
    $(elm).addClass(to);
    $(elm).removeClass(from);
};


$( document ).ready(function(){
    Clinch.AttachEvents();

    var $container = $('#pr-container');
    $container.masonry({
      itemSelector: '.pull_request',
      isAnimated: true,
      animationOptions: {
          duration: 750,
          easing: 'linear',
          queue: false
      }
    });
});
