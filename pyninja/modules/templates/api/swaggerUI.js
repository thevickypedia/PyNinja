document.addEventListener('DOMContentLoaded', () => {
    const waitForLinks = () => {
        // Get all anchor elements with href starting with '#'
        const anchors = document.querySelectorAll('a[href^="#"]');
        if (anchors.length === 0) {
            setTimeout(waitForLinks, 100);
        } else {
            anchors.forEach(anchor => {
                // console.log("Attaching listener to:", anchor.href);  // debug statement
                anchor.addEventListener('click', function (event) {
                    const hrefAttr = anchor.getAttribute('href').substring(1);
                    // legacy approach - scroll stops halfway through
                    // const targetElement = document.querySelector(`a[href='#${hrefAttr}']`);
                    // this is a hacky way to scroll to the correct element
                    const hrefKey = hrefAttr.replace('/default/', 'operations-default-');
                    const targetElement = document.getElementById(hrefKey);
                    if (targetElement) {
                        targetElement.scrollIntoView({
                            behavior: 'smooth'
                        });
                        const expandButton = targetElement.querySelector(".opblock-control-arrow");
                        if (expandButton && expandButton.hasAttribute("aria-expanded")) {
                            expandButton.setAttribute("aria-expanded", "true");
                            expandButton.click();
                        } else {
                            console.error(`Element with id '${hrefKey}' does not have an expand button`);
                        }
                    } else {
                        console.error(`Element with id '${hrefKey}' not found`);
                    }
                });
            });
        }
    };
    waitForLinks();
});
