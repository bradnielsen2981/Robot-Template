/* This is your dashboard javascript, it has been embedded into dashboard.html */
alert("Loaded");

turn_on_detection_button.onclick = turn_on_detection;
function turn_on_detection()
{
    new_ajax_helper('/turn_on_detection');
}

turn_off_detection_button.onclick = turn_off_detection;
function turn_off_detection()
{
    new_ajax_helper('/turn_off_detection');
}
